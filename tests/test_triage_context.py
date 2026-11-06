"""Guest pet context, result follow-ups, ordering and question navigation."""
import json

import pytest
from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import GuestContext, Pet, Sex, Species, TriageAnswerRequest, TriageResult, TriageSession, UrgencyLevel
from app.services import triage_engine
from app.services.life_stage_calculator import calculate_life_stage
from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401
from tests.test_backend import complete_remaining_questions, db, load_content  # noqa: F401

VOMIT_HOME = {'q-vomit-001': 'Once', 'q-vomit-002': 'No, neither', 'q-vomit-003': 'No', 'q-vomit-004': 'Normal energy and appetite'}


def guest_pet(db, species=Species.dog, **context):
    pet = triage_engine.apply_guest_context(Pet(name='Guest pet', species=species), GuestContext(**context) if context else None)
    db.add(pet); db.commit(); db.refresh(pet)
    return pet


def run_check(db, pet, symptom, answers=None, language='en'):
    session, _ = triage_engine.start_session(db, pet, symptom)
    for question_id, answer in (answers or {}).items():
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id=question_id, answer=answer))
    complete_remaining_questions(db, session.id)
    return triage_engine.compute_result(db, session.id, language)


@pytest.mark.parametrize(('species', 'age_group', 'stage'), [
    (Species.dog, 'young', 'puppy'), (Species.cat, 'young', 'kitten'),
    (Species.dog, 'senior', 'senior'), (Species.cat, 'senior', 'senior'),
])
def test_guest_age_group_sets_life_stage(db, species, age_group, stage):
    pet = guest_pet(db, species, age_group=age_group)
    assert calculate_life_stage(pet) == stage
    assert triage_engine.guest_age_group(pet) == age_group


def test_guest_puppy_vomiting_is_vet_soon(db):
    result = run_check(db, guest_pet(db, age_group='young'), 'vomiting', VOMIT_HOME)
    assert result.resulting_urgency == UrgencyLevel.vet_soon
    assert any(reason.kind == 'life_stage' for reason in result.reasons)
    assert result.pet.age_group == 'young' and result.pet.life_stage == 'puppy'
    assert result.pet.date_of_birth is None  # The stand-in date is not reported as a birth date.


def test_guest_young_or_senior_diarrhoea_is_vet_soon(db):
    assert run_check(db, guest_pet(db, Species.cat, age_group='young'), 'diarrhea').resulting_urgency == UrgencyLevel.vet_soon
    assert run_check(db, guest_pet(db, Species.dog, age_group='senior'), 'diarrhea').resulting_urgency == UrgencyLevel.vet_soon
    assert run_check(db, guest_pet(db, Species.dog, age_group='adult'), 'diarrhea').resulting_urgency == UrgencyLevel.monitor_home


@pytest.mark.parametrize('symptom', ['increased_thirst', 'vaginal_discharge'])
def test_guest_intact_female_gets_pyometra_emergency(db, symptom):
    result = run_check(db, guest_pet(db, age_group='adult', sex=Sex.female, neutered=False), symptom)
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    assert result.matched_condition_ids == ['dog-cat-repro-001']
    assert result.pet.age_group == 'adult' and result.pet.life_stage is None
    assert result.context_notes == []


def test_guest_female_of_unknown_age_still_gets_pyometra(db):
    result = run_check(db, guest_pet(db, Species.cat, sex=Sex.female, neutered=False), 'increased_thirst')
    assert result.resulting_urgency == UrgencyLevel.emergency_now


def test_guest_adult_matches_conditions_for_any_adult_stage(db):
    # Mammary guidance is scoped to mature adults and seniors; a guest "adult" may be either.
    pet = guest_pet(db, Species.cat, age_group='adult', sex=Sex.female)
    assert triage_engine._pet_matches_condition_scope(pet, content_library.condition_by_id('dog-cat-repro-002'))


@pytest.mark.parametrize('symptom', ['vomiting', 'increased_thirst', 'diarrhea'])
def test_unknown_guest_context_keeps_todays_urgency(db, symptom):
    answers = VOMIT_HOME if symptom == 'vomiting' else None
    unknown = run_check(db, guest_pet(db), symptom, answers)
    not_sure = run_check(db, guest_pet(db, age_group=None, sex=None, neutered=None), symptom, answers)
    expected = {'vomiting': UrgencyLevel.monitor_home, 'increased_thirst': UrgencyLevel.vet_24h, 'diarrhea': UrgencyLevel.monitor_home}[symptom]
    assert unknown.resulting_urgency == not_sure.resulting_urgency == expected
    assert unknown.matched_condition_ids == not_sure.matched_condition_ids


def test_unknown_context_says_which_detail_would_change_the_guidance(db):
    result = run_check(db, guest_pet(db), 'increased_thirst')
    assert result.resulting_urgency == UrgencyLevel.vet_24h
    note = next(note for note in result.context_notes if note.kind == 'missing_context')
    assert note.urgency == UrgencyLevel.emergency_now
    assert 'female' in note.detail and 'not spayed or neutered' in note.detail
    assert 'sex and spay/neuter status' in note.detail and 'Emergency veterinary care now' in note.detail
    # Known sex, unknown neuter status: only the missing detail is named.
    partial = run_check(db, guest_pet(db, sex=Sex.female), 'increased_thirst')
    assert 'spay/neuter status' in partial.context_notes[0].detail and 'sex and' not in partial.context_notes[0].detail
    # Known out-of-scope details produce no note.
    assert run_check(db, guest_pet(db, sex=Sex.male), 'increased_thirst').context_notes == []


def test_unknown_age_names_the_life_stage_escalation(db):
    result = run_check(db, guest_pet(db, sex=Sex.male, neutered=True), 'vomiting', VOMIT_HOME)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
    notes = [note for note in result.context_notes if note.kind == 'missing_life_stage']
    assert len(notes) == 1 and 'puppy or senior' in notes[0].detail and notes[0].urgency == UrgencyLevel.vet_soon
    assert 'kitten' not in run_check(db, guest_pet(db, sex=Sex.male), 'diarrhea').context_notes[0].detail


@pytest.mark.parametrize('language', ['pt', 'es'])
def test_context_notes_and_recheck_are_translated(db, language):
    result = run_check(db, guest_pet(db), 'increased_thirst', language=language)
    assert result.context_notes and 'female' not in result.context_notes[0].detail
    home = run_check(db, guest_pet(db, sex=Sex.male, neutered=True), 'vomiting', VOMIT_HOME, language)
    english = run_check(db, guest_pet(db, sex=Sex.male, neutered=True), 'vomiting', VOMIT_HOME)
    assert home.recheck_advice and home.recheck_advice != english.recheck_advice
    assert home.watch_for[0].description != english.watch_for[0].description


def test_result_lists_signs_to_watch_for_and_recheck_for_home_care(db):
    result = run_check(db, guest_pet(db, sex=Sex.male), 'vomiting', VOMIT_HOME)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
    assert '24–48 hours' in result.recheck_advice
    flags = content_library.condition_by_id('dog-gi-001').red_flags
    assert {item.description for item in result.watch_for} == {flag.description for flag in flags}
    ranks = [item.urgency.rank for item in result.watch_for]
    assert ranks == sorted(ranks, reverse=True)
    assert result.watch_for[0].description == 'Blood in the vomit'
    urgent = run_check(db, guest_pet(db), 'vomiting', {'q-vomit-001': 'Once', 'q-vomit-002': 'Yes'})
    assert urgent.resulting_urgency == UrgencyLevel.emergency_now and urgent.recheck_advice is None and urgent.watch_for


def test_old_snapshots_without_new_fields_still_validate():
    result = TriageResult.model_validate({'session_id': 's', 'resulting_urgency': 'vet_soon', 'resulting_guidance': 'Old', 'matched_condition_ids': [], 'pet': {'name': 'Rex', 'species': 'dog'}})
    assert result.watch_for == [] and result.recheck_advice is None and result.context_notes == [] and result.pet.age_group is None


def test_possible_causes_keep_authored_order(db):
    result = run_check(db, guest_pet(db, sex=Sex.male), 'vomiting', VOMIT_HOME)
    assert result.possible_causes == content_library.condition_by_id('dog-gi-001').possible_causes
    assert result.possible_causes[-1].startswith('Less commonly')
    assert triage_engine._ordered_unique(['b', 'a', 'b', 'c', 'a']) == ['b', 'a', 'c']


def test_yes_does_not_trigger_the_sunken_eyes_flag(db):
    result = run_check(db, guest_pet(db, sex=Sex.male), 'diarrhea', {'q-diarrhea-001': 'No', 'q-diarrhea-002': 'Yes'})
    assert result.resulting_urgency == UrgencyLevel.vet_24h  # From the question's own rule.
    assert {reason.kind for reason in result.reasons} == {'answer'}


def test_once_does_not_trigger_the_monthly_hairball_flag(db):
    pet = guest_pet(db, Species.cat, age_group='adult', sex=Sex.male, neutered=True)
    result = run_check(db, pet, 'vomiting', VOMIT_HOME)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
    assert all(reason.kind != 'red_flag' for reason in result.reasons)


def test_go_back_rewinds_one_answer(db):
    pet = guest_pet(db)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    assert triage_engine.progress(session) == {'step': 1, 'max_steps': 4}
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-001', answer='2-3 times'))
    session, _, _ = triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-002', answer='No, neither'))
    assert triage_engine.progress(session) == {'step': 3, 'max_steps': 4}
    session, question = triage_engine.go_back(db, session.id, 'q-vomit-003')
    assert question.id == 'q-vomit-002' and session.current_question_id == 'q-vomit-002'
    assert json.loads(session.answers_json) == {'q-vomit-001': '2-3 times'}
    # A stale client still showing question 3 cannot rewind again.
    with pytest.raises(triage_engine.InvalidAnswerError):
        triage_engine.go_back(db, session.id, 'q-vomit-003')
    session, question = triage_engine.go_back(db, session.id, 'q-vomit-002')
    assert question.id == 'q-vomit-001' and json.loads(session.answers_json) == {}
    with pytest.raises(triage_engine.InvalidAnswerError):
        triage_engine.go_back(db, session.id, 'q-vomit-001')  # Nothing earlier.
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-001', answer='Once'))
    assert json.loads(db.get(TriageSession, session.id).answers_json) == {'q-vomit-001': 'Once'}


def test_completed_check_cannot_go_back(db):
    pet = guest_pet(db)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-001', answer='Once'))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-002', answer='Yes'))
    with pytest.raises(triage_engine.InvalidAnswerError):
        triage_engine.go_back(db, session.id, 'q-vomit-002')
    assert triage_engine.compute_result(db, session.id).resulting_urgency == UrgencyLevel.emergency_now


def test_stale_go_back_cannot_overwrite_a_newer_answer(db):
    pet = guest_pet(db)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-001', answer='Once'))
    with Session(db.bind, expire_on_commit=False) as stale_db:
        assert stale_db.get(TriageSession, session.id).current_question_id == 'q-vomit-002'
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-002', answer='Yes'))
        with pytest.raises(triage_engine.InvalidAnswerError):
            triage_engine.go_back(stale_db, session.id, 'q-vomit-002')
    assert triage_engine.compute_result(db, session.id).resulting_urgency == UrgencyLevel.emergency_now


def test_api_guest_context_progress_and_back(client):
    started = client.post('/triage/start', json={'symptom_tag': 'vomiting', 'species': 'dog', 'guest_context': {'age_group': 'young', 'sex': 'male', 'neutered': None}})
    assert started.status_code == 200
    body = started.json()
    assert body['progress'] == {'step': 1, 'max_steps': 4}
    session_id, headers = body['session_id'], {'X-Guest-Token': body['guest_token']}
    answered = client.post(f'/triage/{session_id}/answer', json={'question_id': 'q-vomit-001', 'answer': 'Once'}, headers=headers).json()
    assert answered['progress'] == {'step': 2, 'max_steps': 4}
    assert client.post(f'/triage/{session_id}/back', json={'question_id': 'q-vomit-002'}).status_code == 404  # Guest token required.
    back = client.post(f'/triage/{session_id}/back', json={'question_id': 'q-vomit-002'}, headers=headers)
    assert back.status_code == 200 and back.json()['next_question']['id'] == 'q-vomit-001' and back.json()['progress']['step'] == 1
    assert client.post(f'/triage/{session_id}/back', json={'question_id': 'q-vomit-001'}, headers=headers).status_code == 409
    question = back.json()['next_question']
    while question:
        response = client.post(f'/triage/{session_id}/answer', json={'question_id': question['id'], 'answer': VOMIT_HOME[question['id']]}, headers=headers).json()
        question = response['next_question']
    assert response['progress'] is None
    result = client.get(f'/triage/{session_id}/result', headers=headers).json()
    assert result['resulting_urgency'] == 'vet_soon' and result['pet']['age_group'] == 'young' and result['pet']['sex'] == 'male'
    assert result['watch_for'] and result['recheck_advice'] is None


def test_api_rejects_invalid_guest_context_and_ignores_it_for_saved_pets(client):
    assert client.post('/triage/start', json={'symptom_tag': 'vomiting', 'guest_context': {'age_group': 'ancient'}}).status_code == 422
    headers = signup(client, 'context@example.com')
    pet = client.post('/pets', json={'name': 'Rex', 'species': 'dog'}, headers=headers).json()
    started = client.post('/triage/start', json={'pet_id': pet['id'], 'symptom_tag': 'vomiting', 'guest_context': {'age_group': 'young', 'sex': 'female'}}, headers=headers)
    assert started.status_code == 200
    with Session(test_engine) as db:
        saved = db.get(Pet, pet['id'])
        assert saved.date_of_birth is None and saved.sex is None
