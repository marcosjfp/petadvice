from datetime import date, timedelta

import pytest
from sqlmodel import Session, select

from app.models.schema import AuthSession, GuestAccess, Pet, TriageSession
from app.services.auth import utcnow
from tests.test_auth import client, reset_db, signup, test_engine  # noqa: F401  (shared fixtures)


def make_pet(client, headers, **overrides):
    response = client.post('/pets', json={'name': 'Rex', 'species': 'dog', **overrides}, headers=headers)
    assert response.status_code == 200
    return response.json()


def age_password_confirmations():
    """Make every session's password confirmation old so recent-auth checks fail."""
    with Session(test_engine) as db:
        for session in db.exec(select(AuthSession)).all():
            session.authenticated_at = utcnow() - timedelta(hours=1)
            db.add(session)
        db.commit()


def test_owner_can_edit_pet_and_life_stage_updates(client):
    headers = signup(client, 'edit@example.com')
    pet = make_pet(client, headers)
    assert pet['life_stage'] is None
    birth = (date.today() - timedelta(days=365 * 9)).isoformat()
    response = client.patch(f"/pets/{pet['id']}", json={'name': '  Rexy ', 'date_of_birth': birth, 'breed_size': 'giant', 'sex': 'male', 'neutered': True}, headers=headers)
    assert response.status_code == 200
    updated = response.json()
    assert updated['name'] == 'Rexy'
    assert updated['life_stage'] == 'senior'
    assert updated['neutered'] is True
    # Omitted fields are unchanged; an explicit null clears an optional detail.
    cleared = client.patch(f"/pets/{pet['id']}", json={'date_of_birth': None}, headers=headers).json()
    assert cleared['date_of_birth'] is None and cleared['life_stage'] is None
    assert cleared['sex'] == 'male' and cleared['name'] == 'Rexy'
    assert client.get(f"/pets/{pet['id']}", headers=headers).json()['name'] == 'Rexy'


@pytest.mark.parametrize('payload', [
    {'name': '   '}, {'name': None}, {'name': 'x' * 101},
    {'date_of_birth': (date.today() + timedelta(days=1)).isoformat()},
    {'sex': 'unknown'}, {'breed_size': 'tiny'}, {'neutered': 'maybe'},
    {'species': 'cat'}, {'species': 'both'}, {'weight_kg': 0},
])
def test_pet_update_is_validated(client, payload):
    headers = signup(client, 'validate-edit@example.com')
    pet = make_pet(client, headers)
    assert client.patch(f"/pets/{pet['id']}", json=payload, headers=headers).status_code == 422
    assert client.get(f"/pets/{pet['id']}", headers=headers).json()['name'] == 'Rex'


def test_unchanged_species_may_be_echoed(client):
    headers = signup(client, 'echo@example.com')
    pet = make_pet(client, headers)
    assert client.patch(f"/pets/{pet['id']}", json={'species': 'dog', 'name': 'Rex II'}, headers=headers).status_code == 200


def test_other_owner_cannot_edit_or_delete_pet(client):
    owner = signup(client, 'owner@example.com')
    pet = make_pet(client, owner)
    stranger = signup(client, 'stranger@example.com')
    assert client.patch(f"/pets/{pet['id']}", json={'name': 'Stolen'}, headers=stranger).status_code == 404
    assert client.delete(f"/pets/{pet['id']}", headers=stranger).status_code == 404
    assert client.get(f"/pets/{pet['id']}", headers=owner).json()['name'] == 'Rex'
    assert client.patch('/pets/missing', json={'name': 'Ghost'}, headers=owner).status_code == 404
    client.cookies.clear()
    assert client.patch(f"/pets/{pet['id']}", json={'name': 'Anon'}).status_code == 401
    assert client.delete(f"/pets/{pet['id']}").status_code == 401


def test_pet_edit_rejects_cross_origin_cookie_requests(client):
    signup(client, 'csrf-edit@example.com')
    origin = {'Origin': 'http://localhost:5173'}
    pet = client.post('/pets', json={'name': 'Miso', 'species': 'cat'}, headers=origin).json()
    assert client.patch(f"/pets/{pet['id']}", json={'name': 'X'}, headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.delete(f"/pets/{pet['id']}", headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.patch(f"/pets/{pet['id']}", json={'name': 'Mochi'}, headers=origin).json()['name'] == 'Mochi'


def test_delete_requires_recent_password_and_cascades_checks(client):
    headers = signup(client, 'delete@example.com')
    pet = make_pet(client, headers)
    keep = make_pet(client, headers, name='Miso', species='cat')
    session_id = client.post('/triage/start', json={'pet_id': pet['id'], 'symptom_tag': 'scratching'}, headers=headers).json()['session_id']
    kept_session = client.post('/triage/start', json={'pet_id': keep['id'], 'symptom_tag': 'vomiting'}, headers=headers).json()['session_id']
    with Session(test_engine) as db:  # A stray guest capability row must not block the cascade.
        db.add(GuestAccess(session_id=session_id, token_hash='x', expires_at=utcnow()))
        db.commit()
    age_password_confirmations()
    assert client.delete(f"/pets/{pet['id']}", headers=headers).status_code == 403
    assert client.post('/auth/reauthenticate', json={'password': 'a-long-test-passphrase'}, headers=headers).status_code == 200
    assert client.delete(f"/pets/{pet['id']}", headers=headers).status_code == 200
    assert client.get(f"/pets/{pet['id']}", headers=headers).status_code == 404
    with Session(test_engine) as db:
        assert db.get(Pet, pet['id']) is None
        assert db.get(TriageSession, session_id) is None
        assert db.get(GuestAccess, session_id) is None
        assert db.get(TriageSession, kept_session) is not None
    assert [item['id'] for item in client.get('/pets', headers=headers).json()] == [keep['id']]
