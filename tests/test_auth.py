import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app


test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


def _override_get_session():
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session


@pytest.fixture(autouse=True)
def reset_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def signup(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/auth/signup",
        json={
            "email": email,
            "password": "hunter22pw",
            "privacy_policy_accepted": True,
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_signup_login_and_me(client):
    headers = signup(client, "test@example.com")
    login = client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "hunter22pw"},
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
        json={"email": "no-consent@example.com", "password": "hunter22pw", "privacy_policy_accepted": False},
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
