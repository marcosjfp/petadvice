import json
from datetime import timedelta

from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import Pet, TriageSession, UrgencyLevel
from app.services.auth import utcnow
from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401


def complete_check(client, pet_id=None, headers=None):
    started = client.post('/triage/start', json={'pet_id': pet_id, 'symptom_tag': 'vomiting', 'species': 'dog'}, headers=headers).json()
    headers = headers or {'X-Guest-Token': started['guest_token']}
    answers = {'q-vomit-001': 'Once', 'q-vomit-002': 'No, neither', 'q-vomit-003': 'No', 'q-vomit-004': 'Normal energy and appetite'}
    question = started['next_question']
    while question:
        response = client.post(f"/triage/{started['session_id']}/answer", json={'question_id': question['id'], 'answer': answers[question['id']]}, headers=headers)
        assert response.status_code == 200
        question = response.json()['next_question']
    return started['session_id'], headers


def test_report_freezes_original_guidance_context_and_content(client, monkeypatch):
    headers = signup(client, 'report@example.com')
    pet = client.post('/pets', json={'name': 'Original name', 'species': 'dog'}, headers=headers).json()
    check, headers = complete_check(client, pet['id'], headers)
    first = client.get(f'/triage/{check}/result', headers=headers).json()
    assert first['resulting_urgency'] == 'monitor_home'
    assert first['reasons'] and first['answers'][0]['prompt'] == content_library.question_by_id('q-vomit-001').prompt
    assert first['answers'][0]['answer'] == 'Once'
    assert len(first['content_version']) == 64 and first['sources']
    assert first['pet']['name'] == 'Original name'
    with Session(test_engine) as db:
        profile = db.get(Pet, pet['id']); profile.name = 'Changed name'; db.add(profile); db.commit()
    condition = content_library.conditions_for_symptom('vomiting')[0]
    monkeypatch.setattr(condition, 'home_care_guidance', 'New content must not replace old advice')
    monkeypatch.setattr(condition, 'urgency_default', UrgencyLevel.emergency_now)
    monkeypatch.setattr(content_library, 'version', 'new-version')
    assert client.get(f'/triage/{check}/result', headers=headers).json() == first
    export = client.get('/auth/me/export', headers=headers).json()
    assert export['triage_sessions'][0]['result_snapshot'] == first


def test_explanation_cites_the_emergency_answer_without_changing_question(client):
    started = client.post('/triage/start', json={'symptom_tag': 'vomiting'}).json()
    headers = {'X-Guest-Token': started['guest_token']}
    question = started['next_question']
    # Follow a valid path until a question offers an emergency escalation.
    while question:
        rule = content_library.question_by_id(question['id'])
        answer = next((answer for answer, level in rule.escalate_if.items() if level == UrgencyLevel.emergency_now), rule.options[0])
        response = client.post(f"/triage/{started['session_id']}/answer", json={'question_id': rule.id, 'answer': answer}, headers=headers)
        assert response.status_code == 200
        question = response.json()['next_question']
    result = client.get(f"/triage/{started['session_id']}/result", headers=headers).json()
    assert result['resulting_urgency'] == 'emergency_now'
    recorded = {item['prompt']: item['answer'] for item in result['answers']}
    assert any(reason['kind'] == 'answer' and any(prompt in reason['detail'] and answer in reason['detail'] for prompt, answer in recorded.items()) for reason in result['reasons'])


def test_legacy_results_keep_saved_guidance_without_invented_explanations(client):
    headers = signup(client, 'legacy-report@example.com')
    pet = client.post('/pets', json={'name': 'Present name', 'species': 'dog'}, headers=headers).json()
    with Session(test_engine) as db:
        check = TriageSession(pet_id=pet['id'], symptom_entry_point='vomiting', current_question_id=None, resulting_urgency=UrgencyLevel.vet_soon, resulting_guidance='The original advice.', answers_json=json.dumps({'old-question': 'Old answer'}), condition_entries_matched_raw='old-condition')
        db.add(check); db.commit(); check_id = check.id
    result = client.get(f'/triage/{check_id}/result', headers=headers).json()
    assert result['historical'] is True and result['resulting_guidance'] == 'The original advice.'
    assert result['resulting_urgency'] == 'vet_soon' and result['matched_condition_ids'] == ['old-condition']
    assert result['reasons'] == [] and result['pet'] is None and result['content_version'] is None
    assert result['sources'] == [] and result['answers'][0]['prompt'] == 'Question ID: old-question'


def test_history_is_paginated_and_private_including_cursor(client):
    headers = signup(client, 'history@example.com')
    pet = client.post('/pets', json={'name': 'Rex', 'species': 'dog'}, headers=headers).json()
    other_pet = client.post('/pets', json={'name': 'Miso', 'species': 'cat'}, headers=headers).json()
    with Session(test_engine) as db:
        for index in range(23):
            db.add(TriageSession(id=f'check-{index:02}', pet_id=pet['id'], started_at=utcnow()-timedelta(days=index), symptom_entry_point='vomiting', current_question_id=None))
        db.add(TriageSession(id='other-check', pet_id=other_pet['id'], symptom_entry_point='vomiting'))
        db.commit()
    endpoint = f"/triage/history/{pet['id']}"
    first = client.get(endpoint, headers=headers).json()
    assert len(first['checks']) == 20 and first['next_cursor'] == 'check-19'
    second = client.get(endpoint, params={'before': first['next_cursor']}, headers=headers).json()
    assert len(second['checks']) == 3 and second['next_cursor'] is None
    assert not set(check['session_id'] for check in first['checks']) & set(check['session_id'] for check in second['checks'])
    assert client.get(endpoint, params={'before': 'other-check'}, headers=headers).status_code == 404
    stranger = signup(client, 'other-history@example.com')
    assert client.get(endpoint, headers=stranger).status_code == 404
    client.cookies.clear()
    assert client.get(endpoint).status_code == 401
