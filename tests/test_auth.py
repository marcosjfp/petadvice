import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app
import importlib


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def _override_get_session():
    with Session(test_engine) as session:
        yield session


@pytest.fixture(autouse=True)
def reset_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def client(monkeypatch):
    # API tests must never initialize or migrate the developer's real database.
    monkeypatch.setattr(importlib.import_module("app.main"), "init_db", lambda: None)
    app.dependency_overrides[get_session] = _override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def signup(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "a-long-test-passphrase",
            "privacy_policy_accepted": True,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_signup_login_and_me(client):
    headers = signup(client, "test@example.com")
    login = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "a-long-test-passphrase"},
    )
    assert login.status_code == 200
    assert client.get("/auth/me", headers=headers).json()["email"] == "test@example.com"


def test_wrong_password_and_unauthorized_pets_are_rejected(client):
    signup(client, "wrongpw@example.com")
    wrong_password = client.post(
        "/auth/login",
        json={"email": "wrongpw@example.com", "password": "incorrect"},
    )
    assert wrong_password.status_code == 401
    client.cookies.clear()
    assert client.get("/pets").status_code == 401


def test_pet_is_visible_only_to_its_owner(client):
    owner_headers = signup(client, "petowner@example.com")
    created = client.post(
        "/pets",
        json={"name": "Rex", "species": "dog"},
        headers=owner_headers,
    )
    assert created.status_code == 200
    pet_id = created.json()["id"]
    assert any(item["id"] == pet_id for item in client.get("/pets", headers=owner_headers).json())

    other_headers = signup(client, "other@example.com")
    assert client.get(f"/pets/{pet_id}", headers=other_headers).status_code == 404
    assert client.post(
        "/triage/start",
        json={"pet_id": pet_id, "symptom_tag": "vomiting"},
        headers=other_headers,
    ).status_code == 404


def test_signup_validation_and_data_lifecycle(client):
    short = client.post(
        "/auth/signup",
        json={"email": "short@example.com", "password": "short", "privacy_policy_accepted": True},
    )
    no_consent = client.post(
        "/auth/signup",
        json={"email": "no-consent@example.com", "password": "a-long-test-passphrase", "privacy_policy_accepted": False},
    )
    assert short.status_code == 422
    assert no_consent.status_code == 422

    headers = signup(client, "lifecycle@example.com")
    pet = client.post("/pets", json={"name": "Miso", "species": "cat"}, headers=headers).json()
    export = client.get("/auth/me/export", headers=headers)
    assert export.status_code == 200
    assert export.json()["pets"][0]["id"] == pet["id"]

    deleted = client.delete("/auth/me", headers=headers)
    assert deleted.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_guest_can_complete_quick_check_without_login(client):
    started = client.post(
        "/triage/start",
        json={"symptom_tag": "vomiting", "species": "dog"},
    )
    assert started.status_code == 200
    session_id = started.json()["session_id"]
    question = started.json()["next_question"]
    answers = {
        "q-vomit-001": "Once",
        "q-vomit-002": "No, neither",
        "q-vomit-003": "No",
        "q-vomit-004": "Normal energy and appetite",
    }
    while question is not None:
        answer = answers[question["id"]]
        response = client.post(
            f"/triage/{session_id}/answer",
            json={"question_id": question["id"], "answer": answer},
        )
        assert response.status_code == 200
        question = response.json()["next_question"]
    result = client.get(f"/triage/{session_id}/result")
    assert result.status_code == 200
    assert result.json()["resulting_urgency"] == "monitor_home"


def test_email_normalization_and_password_bounds(client):
    headers = signup(client, '  CASE@EXAMPLE.COM ')
    assert client.get('/auth/me', headers=headers).json()['email'] == 'case@example.com'
    duplicate = client.post('/auth/signup', json={'email': 'case@example.com', 'password': 'a-long-test-passphrase', 'privacy_policy_accepted': True})
    assert duplicate.status_code == 400
    for email, password in [('invalid', 'a-long-test-passphrase'), ('long@example.com', 'x' * 129), ('short@example.com', 'x' * 14)]:
        assert client.post('/auth/signup', json={'email': email, 'password': password, 'privacy_policy_accepted': True}).status_code == 422


def test_cookie_session_csrf_logout_and_cache_headers(client):
    signup(client, 'cookie@example.com')
    assert 'HttpOnly' in client.post('/auth/login', json={'email': 'cookie@example.com', 'password': 'a-long-test-passphrase'}).headers['set-cookie']
    assert client.get('/auth/me').status_code == 200
    assert client.get('/auth/me').headers['cache-control'] == 'no-store'
    payload = {'name': 'Miso', 'species': 'cat'}
    assert client.post('/pets', json=payload, headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.post('/pets', json=payload).status_code == 403
    assert client.post('/pets', json=payload, headers={'Origin': 'http://localhost:5173'}).status_code == 200
    assert client.post('/auth/logout').status_code == 200
    assert client.get('/auth/me').status_code == 401


@pytest.mark.parametrize('payload', [
    {'name': '   ', 'species': 'dog'}, {'name': 'Miso', 'species': 'both'},
    {'name': 'Miso', 'species': 'dog', 'date_of_birth': '2999-01-01'},
    {'name': 'Miso', 'species': 'dog', 'weight_kg': -1},
])
def test_invalid_pet_profile_rejected(client, payload):
    headers = signup(client, 'validation@example.com')
    assert client.post('/pets', json=payload, headers=headers).status_code == 422


def test_new_pet_immediately_has_life_stage(client):
    headers = signup(client, 'care@example.com')
    from datetime import date, timedelta
    pet = client.post('/pets', json={'name': '  Miso  ', 'species': 'cat', 'date_of_birth': (date.today() - timedelta(days=730)).isoformat()}, headers=headers).json()
    assert pet['name'] == 'Miso'
    assert pet['life_stage'] == 'young_adult'


def test_unknown_and_incomplete_guest_checks(client):
    from app.models.schema import Pet
    from sqlmodel import select
    assert client.post('/triage/start', json={'symptom_tag': 'nonsense'}).status_code == 422
    assert client.post('/triage/start', json={'symptom_tag': 'vomiting', 'species': 'both'}).status_code == 422
    with Session(test_engine) as db:
        assert db.exec(select(Pet)).all() == []
    started = client.post('/triage/start', json={'symptom_tag': 'vomiting'}).json()
    assert client.get(f"/triage/{started['session_id']}/result").status_code == 409


def test_production_requires_secret(monkeypatch):
    from app.services.auth import validate_auth_configuration
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.delenv('JWT_SECRET_KEY', raising=False)
    with pytest.raises(RuntimeError):
        validate_auth_configuration()
    monkeypatch.setenv('JWT_SECRET_KEY', 'a' * 48)
    monkeypatch.setenv('CORS_ORIGINS', 'https://petadvice.example.com')
    validate_auth_configuration()


def test_tokens_require_expiration():
    import jwt
    from app.services.auth import SECRET_KEY, decode_access_token
    from fastapi import HTTPException
    token = jwt.encode({'sub': 'owner', 'iat': 1, 'iss': 'petadvice', 'aud': 'petadvice-api'}, SECRET_KEY, algorithm='HS256')
    with pytest.raises(HTTPException) as error:
        decode_access_token(token)
    assert error.value.status_code == 401


def test_legacy_bcrypt_login_upgrades_hash(client):
    import bcrypt
    from app.models.schema import Owner
    password = 'old-password'
    with Session(test_engine) as db:
        owner = Owner(email='legacy@example.com', hashed_password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode())
        db.add(owner); db.commit(); db.refresh(owner)
        owner_id = owner.id
    assert client.post('/auth/login', json={'email': 'legacy@example.com', 'password': password}).status_code == 200
    with Session(test_engine) as db:
        assert db.get(Owner, owner_id).hashed_password.startswith('$argon2id$')


def test_account_checks_and_export_stay_private(client):
    headers = signup(client, 'private@example.com')
    pet = client.post('/pets', json={'name': 'Rex', 'species': 'dog'}, headers=headers).json()
    started = client.post('/triage/start', json={'pet_id': pet['id'], 'symptom_tag': 'scratching'}, headers=headers).json()
    session_id = started['session_id']
    other = signup(client, 'stranger@example.com')
    assert client.get(f'/triage/{session_id}/result', headers=other).status_code == 404
    client.cookies.clear()
    assert client.get(f'/triage/{session_id}/result').status_code == 401
    export = client.get('/auth/me/export', headers=headers).json()
    assert 'hashed_password' not in export['owner']
    assert len(export['triage_sessions']) == 1


def test_cross_origin_login_is_rejected(client):
    response = client.post('/auth/login', json={'email': 'test@example.com', 'password': 'password'}, headers={'Origin': 'https://attacker.example'})
    assert response.status_code == 403


def test_invalid_cookie_is_cleared_so_guest_check_still_works(client):
    from app.services.auth import COOKIE_NAME
    client.cookies.set(COOKIE_NAME, 'expired-token', domain='testserver.local', path='/')
    rejected = client.get('/auth/me')
    assert rejected.status_code == 401
    assert 'Max-Age=0' in rejected.headers['set-cookie']
    assert client.post('/triage/start', json={'symptom_tag': 'vomiting'}).status_code == 200
