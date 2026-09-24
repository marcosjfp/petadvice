# PETAdvice — Phase 2: Accounts, Login, and Pets Tied to an Owner

> Adds real signup/login (email + password, JWT-based) and switches pets from the `demo-owner` placeholder to the authenticated user — plus the GDPR touchpoints the build guide flagged as "build now, not later": explicit consent at signup, a data export endpoint, and an account-deletion endpoint that cascades to pets and triage sessions.
>
> **Scope decision:** self-rolled FastAPI + JWT auth, not Firebase Auth. The build guide raised Firebase as an option mainly because push notifications would need Firebase anyway — but that hasn't been built yet, and shipping login now shouldn't wait on a Firebase project setup. This is fully replaceable later without touching the rest of the app, since every other endpoint only depends on `get_current_owner`, not on how it authenticates.

---

## 1. New dependencies — add to `requirements.txt`

```text
bcrypt>=4.0
pyjwt>=2.9
```

## 2. Schema changes — add to `app/models/schema.py`

Add `field_validator` to the existing pydantic import line:

```python
from pydantic import BaseModel, field_validator
```

Replace the `Owner` model with this (adds password + consent tracking):

```python
class Owner(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    consent_given_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

Remove `owner_id` from `PetCreate` — it now comes from the authenticated token, never from the request body (a client could otherwise create pets under someone else's account by just changing a field):

```python
class PetCreate(BaseModel):
    name: str
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[EnvironmentFactor] = []
```

Add these new request/response shapes (near the other API shapes at the bottom of the file):

```python
class OwnerSignup(BaseModel):
    email: str
    password: str
    privacy_policy_accepted: bool

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("privacy_policy_accepted")
    @classmethod
    def must_accept_privacy_policy(cls, v: bool) -> bool:
        if not v:
            raise ValueError("You must accept the privacy policy to create an account")
        return v


class OwnerLogin(BaseModel):
    email: str
    password: str


class OwnerPublic(BaseModel):
    id: str
    email: str
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

---

## 3. New file — `app/services/auth.py`

```python
# app/services/auth.py
"""
Password hashing + JWT issuing/verification for owner accounts.

JWT_SECRET_KEY MUST be overridden via an environment variable in any
real deployment — the default below is for local dev only and must
never reach a deployed environment.
"""
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from app.db import get_session
from app.models.schema import Owner

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

_bearer_scheme = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def create_access_token(owner_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": owner_id, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def get_current_owner(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_session),
) -> Owner:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    owner_id = decode_access_token(credentials.credentials)
    owner = db.get(Owner, owner_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Owner not found")
    return owner
```

`auto_error=False` plus the manual check is deliberate — the default `HTTPBearer` behavior returns 403 for a missing header, which is the wrong status code here; every authentication failure (missing, invalid, or expired token, or a deleted owner) should come back as 401.

---

## 4. New file — `app/api/auth.py`

```python
# app/api/auth.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import (
    Owner,
    OwnerLogin,
    OwnerPublic,
    OwnerSignup,
    Pet,
    TokenResponse,
    TriageSession,
)
from app.services.auth import create_access_token, get_current_owner, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: OwnerSignup, db: Session = Depends(get_session)):
    existing = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    owner = Owner(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return TokenResponse(access_token=create_access_token(owner.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: OwnerLogin, db: Session = Depends(get_session)):
    owner = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if owner is None or not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(owner.id))


@router.get("/me", response_model=OwnerPublic)
def read_current_owner(current_owner: Owner = Depends(get_current_owner)):
    return current_owner


@router.get("/me/export")
def export_my_data(current_owner: Owner = Depends(get_current_owner), db: Session = Depends(get_session)):
    """GDPR Article 15 (right of access) — everything held about this owner."""
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    pet_ids = [p.id for p in pets]
    sessions = (
        db.exec(select(TriageSession).where(TriageSession.pet_id.in_(pet_ids))).all() if pet_ids else []
    )
    return {
        "owner": current_owner.model_dump(exclude={"hashed_password"}),
        "pets": [p.model_dump() for p in pets],
        "triage_sessions": [s.model_dump() for s in sessions],
    }


@router.delete("/me")
def delete_my_account(current_owner: Owner = Depends(get_current_owner), db: Session = Depends(get_session)):
    """GDPR Article 17 (right to erasure) — cascades to pets and their triage sessions."""
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    for pet in pets:
        sessions = db.exec(select(TriageSession).where(TriageSession.pet_id == pet.id)).all()
        for s in sessions:
            db.delete(s)
        db.delete(pet)
    db.delete(current_owner)
    db.commit()
    return {"status": "account and all associated data deleted"}
```

---

## 5. Secure the pets endpoints — replace `app/api/pets.py`

Pets are now created under, and only ever visible to, the authenticated owner — `owner_id` is gone from the request entirely:

```python
# app/api/pets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import Owner, Pet, PetCreate
from app.services.auth import get_current_owner
from app.services.life_stage_calculator import calculate_life_stage

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=Pet)
def create_pet(
    payload: PetCreate,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pet = Pet(
        owner_id=current_owner.id,
        **payload.model_dump(exclude={"environment_factors"}),
        environment_factors=[f.value for f in payload.environment_factors],
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("/{pet_id}")
def get_pet(
    pet_id: str,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pet = db.get(Pet, pet_id)
    if pet is None or pet.owner_id != current_owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return {**pet.model_dump(), "life_stage": calculate_life_stage(pet)}


@router.get("")
def list_my_pets(
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    return [{**p.model_dump(), "life_stage": calculate_life_stage(p)} for p in pets]
```

A pet belonging to someone else now returns the same 404 as a pet that doesn't exist at all — deliberately, so the API never confirms whether a given `pet_id` belongs to another account.

## 6. Close the same gap on triage — replace `app/api/triage.py`

Without this, an authenticated user could still start or read a triage session for *any* `pet_id`, not just their own:

```python
# app/api/triage.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.content.loader import content_library
from app.db import get_session
from app.models.schema import Owner, Pet, TriageAnswerRequest, TriageSession, TriageStartRequest
from app.services import triage_engine
from app.services.auth import get_current_owner

router = APIRouter(prefix="/triage", tags=["triage"])


def _get_owned_pet(db: Session, pet_id: str, owner: Owner) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None or pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


def _verify_session_ownership(db: Session, session_id: str, owner: Owner) -> None:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Triage session not found")
    pet = db.get(Pet, session.pet_id)
    if pet is None or pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Triage session not found")


@router.get("/questions")
def get_triage_questions(symptom_tag: str):
    return content_library.questions_for_symptom(symptom_tag)


@router.post("/start")
def start_triage(
    payload: TriageStartRequest,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pet = _get_owned_pet(db, payload.pet_id, current_owner)
    session, first_question = triage_engine.start_session(db, pet, payload.symptom_tag)
    return {
        "session_id": session.id,
        "next_question": first_question,
        "flow_complete": first_question is None,
    }


@router.post("/{session_id}/answer")
def answer_triage(
    session_id: str,
    payload: TriageAnswerRequest,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner)
    try:
        _, next_question, flow_complete = triage_engine.answer_question(db, session_id, payload)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    return {"next_question": next_question, "flow_complete": flow_complete}


@router.get("/{session_id}/result")
def get_triage_result(
    session_id: str,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner)
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
```

## 7. Wire up the new router — update `app/main.py`

```python
from app.api import auth, conditions, pets, preventive_care, triage
```

and add, alongside the other `include_router` calls:

```python
app.include_router(auth.router)
```

## 8. Reset your local dev database

`SQLModel.metadata.create_all()` only creates tables that don't exist yet — it won't add the new `hashed_password`/`consent_given_at` columns to an `Owner` table that already exists. For local dev, just delete `petadvice.db` and let it recreate on the next run. (Once there's real user data to preserve, this is exactly what Alembic migrations are for — worth introducing before that point, not after.)

---

## 9. Frontend

### Replace `src/api/client.ts`

```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
const TOKEN_KEY = 'petadvice_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    ...options,
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  signup: (email: string, password: string, privacyPolicyAccepted: boolean) =>
    request<{ access_token: string }>('/auth/signup', {
      method: 'POST',
      body: JSON.stringify({ email, password, privacy_policy_accepted: privacyPolicyAccepted }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  getMe: () => request('/auth/me'),
  createPet: (payload: unknown) => request('/pets', { method: 'POST', body: JSON.stringify(payload) }),
  getPet: (petId: string) => request(`/pets/${petId}`),
  listPets: () => request('/pets'),
  listConditions: (params: Record<string, string>) =>
    request(`/conditions?${new URLSearchParams(params)}`),
  listPreventiveCare: (params: Record<string, string>) =>
    request(`/preventive-care?${new URLSearchParams(params)}`),
  startTriage: (petId: string, symptomTag: string) =>
    request('/triage/start', {
      method: 'POST',
      body: JSON.stringify({ pet_id: petId, symptom_tag: symptomTag }),
    }),
  getTriageQuestions: (symptomTag: string) =>
    request(`/triage/questions?symptom_tag=${encodeURIComponent(symptomTag)}`),
  answerTriage: (sessionId: string, questionId: string, answer: string) =>
    request(`/triage/${sessionId}/answer`, {
      method: 'POST',
      body: JSON.stringify({ question_id: questionId, answer }),
    }),
  getTriageResult: (sessionId: string) => request(`/triage/${sessionId}/result`),
}
```

(`localStorage` for the token is the pragmatic MVP choice — simple, and fine for now — but it is readable by any script on the page, so it's worth revisiting in favor of an httpOnly cookie once there's anything more sensitive riding on session security than there is today.)

### New file — `src/pages/Login.tsx`

```tsx
// src/pages/Login.tsx
import { useState } from 'react'
import { api, setToken } from '../api/client'

export function LoginForm({ onAuthenticated }: { onAuthenticated: () => void }) {
  const [mode, setMode] = useState<'login' | 'signup'>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [privacyAccepted, setPrivacyAccepted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    try {
      const res =
        mode === 'login'
          ? await api.login(email, password)
          : await api.signup(email, password, privacyAccepted)
      setToken((res as any).access_token)
      onAuthenticated()
    } catch {
      setError(
        mode === 'login'
          ? 'Incorrect email or password'
          : 'Could not create account — check the password is 8+ characters and the policy is accepted',
      )
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-sm space-y-3">
      <h2 className="text-lg font-semibold">{mode === 'login' ? 'Log in' : 'Create an account'}</h2>
      <input
        className="w-full rounded border p-2"
        type="email"
        placeholder="Email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <input
        className="w-full rounded border p-2"
        type="password"
        placeholder="Password"
        required
        minLength={8}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      {mode === 'signup' && (
        <label className="flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            checked={privacyAccepted}
            onChange={(e) => setPrivacyAccepted(e.target.checked)}
          />
          <span>I agree to the Privacy Policy</span>
        </label>
      )}
      {error && <p className="text-sm text-red-600">{error}</p>}
      <button className="rounded bg-teal-700 px-4 py-2 text-white" type="submit">
        {mode === 'login' ? 'Log in' : 'Sign up'}
      </button>
      <button
        type="button"
        className="block text-sm text-teal-700 underline"
        onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
      >
        {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Log in'}
      </button>
    </form>
  )
}
```

### Update `src/pages/PetProfile.tsx` — drop the `ownerId` prop

The backend now derives the owner from the token, so the form no longer needs (or should send) it:

```tsx
// src/pages/PetProfile.tsx
import { useState } from 'react'
import { api } from '../api/client'

export function PetProfileForm({ onCreated }: { onCreated: (petId: string) => void }) {
  const [form, setForm] = useState({
    name: '',
    species: 'dog',
    breed: '',
    breed_size: '',
    date_of_birth: '',
    sex: '',
    neutered: false,
    weight_kg: '',
  })

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    const pet = (await api.createPet({
      name: form.name,
      species: form.species,
      breed: form.breed || null,
      breed_size: form.breed_size || null,
      date_of_birth: form.date_of_birth || null,
      sex: form.sex || null,
      neutered: form.neutered,
      weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
      environment_factors: [],
    })) as any
    onCreated(pet.id)
  }

  return (
    <form onSubmit={submit} className="max-w-md space-y-3">
      <input
        className="w-full rounded border p-2"
        placeholder="Name"
        required
        value={form.name}
        onChange={(e) => setForm({ ...form, name: e.target.value })}
      />
      <select
        className="w-full rounded border p-2"
        value={form.species}
        onChange={(e) => setForm({ ...form, species: e.target.value })}
      >
        <option value="dog">Dog</option>
        <option value="cat">Cat</option>
      </select>
      <input
        className="w-full rounded border p-2"
        placeholder="Breed"
        value={form.breed}
        onChange={(e) => setForm({ ...form, breed: e.target.value })}
      />
      <select
        className="w-full rounded border p-2"
        value={form.breed_size}
        onChange={(e) => setForm({ ...form, breed_size: e.target.value })}
      >
        <option value="">Breed size (dogs)</option>
        <option value="small">Small</option>
        <option value="medium">Medium</option>
        <option value="large">Large</option>
        <option value="giant">Giant</option>
      </select>
      <input
        type="date"
        className="w-full rounded border p-2"
        value={form.date_of_birth}
        onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })}
      />
      <select
        className="w-full rounded border p-2"
        value={form.sex}
        onChange={(e) => setForm({ ...form, sex: e.target.value })}
      >
        <option value="">Sex</option>
        <option value="male">Male</option>
        <option value="female">Female</option>
      </select>
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={form.neutered}
          onChange={(e) => setForm({ ...form, neutered: e.target.checked })}
        />
        Neutered / spayed
      </label>
      <input
        className="w-full rounded border p-2"
        placeholder="Weight (kg)"
        type="number"
        value={form.weight_kg}
        onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
      />
      <button className="rounded bg-teal-700 px-4 py-2 text-white" type="submit">
        Save pet
      </button>
    </form>
  )
}
```

### Replace `src/App.tsx`

```tsx
// src/App.tsx
import { useEffect, useState } from 'react'
import { PetProfileForm } from './pages/PetProfile'
import { TriageFlow } from './pages/TriageFlow'
import { ConditionLibrary } from './pages/ConditionLibrary'
import { PreventiveCare } from './pages/PreventiveCare'
import { EmergencyReference } from './components/EmergencyReference'
import { LoginForm } from './pages/Login'
import { api, clearToken, getToken } from './api/client'

export default function App() {
  const [authenticated, setAuthenticated] = useState(false)
  const [checkingAuth, setCheckingAuth] = useState(true)
  const [petId, setPetId] = useState<string | null>(null)
  const [tab, setTab] = useState<'triage' | 'library' | 'preventive'>('triage')

  useEffect(() => {
    async function checkAuth() {
      if (!getToken()) {
        setCheckingAuth(false)
        return
      }
      try {
        await api.getMe()
        setAuthenticated(true)
        const pets = (await api.listPets()) as any[]
        if (pets.length > 0) setPetId(pets[0].id)
      } catch {
        clearToken()
      } finally {
        setCheckingAuth(false)
      }
    }
    checkAuth()
  }, [])

  function logout() {
    clearToken()
    setAuthenticated(false)
    setPetId(null)
  }

  if (checkingAuth) return null

  if (!authenticated) {
    return (
      <div className="mx-auto max-w-2xl p-4">
        <h1 className="text-2xl font-bold text-teal-800">PETAdvice</h1>
        <LoginForm onAuthenticated={() => setAuthenticated(true)} />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl p-4 pb-24">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-teal-800">PETAdvice</h1>
        <button className="text-sm text-gray-500 underline" onClick={logout}>
          Log out
        </button>
      </div>
      {!petId ? (
        <PetProfileForm onCreated={setPetId} />
      ) : (
        <>
          <nav className="my-4 flex gap-2">
            {(['triage', 'library', 'preventive'] as const).map((t) => (
              <button
                key={t}
                className={`rounded px-3 py-1 ${tab === t ? 'bg-teal-700 text-white' : 'border'}`}
                onClick={() => setTab(t)}
              >
                {t}
              </button>
            ))}
          </nav>
          {tab === 'triage' && <TriageFlow petId={petId} />}
          {tab === 'library' && <ConditionLibrary species="dog" />}
          {tab === 'preventive' && <PreventiveCare species="dog" lifeStage="young_adult" />}
        </>
      )}
      <EmergencyReference />
    </div>
  )
}
```

---

## 10. Tests — new file `tests/test_auth.py`

Uses `TestClient` against an isolated in-memory DB (overriding `get_session`), rather than the triage engine's approach of calling service functions directly — auth is fundamentally about HTTP headers and status codes, so it's tested at the API layer:

```python
# tests/test_auth.py
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db import get_session
from app.main import app

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})


def _override_get_session():
    with Session(test_engine) as session:
        yield session


app.dependency_overrides[get_session] = _override_get_session


@pytest.fixture(autouse=True)
def _reset_db():
    SQLModel.metadata.create_all(test_engine)
    yield
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def test_signup_and_login_flow(client):
    signup_res = client.post(
        "/auth/signup",
        json={"email": "test@example.com", "password": "hunter22pw", "privacy_policy_accepted": True},
    )
    assert signup_res.status_code == 200
    assert "access_token" in signup_res.json()

    login_res = client.post("/auth/login", json={"email": "test@example.com", "password": "hunter22pw"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    me_res = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "test@example.com"


def test_login_with_wrong_password_rejected(client):
    client.post(
        "/auth/signup",
        json={"email": "wrongpw@example.com", "password": "correct-pw", "privacy_policy_accepted": True},
    )
    res = client.post("/auth/login", json={"email": "wrongpw@example.com", "password": "incorrect"})
    assert res.status_code == 401


def test_pets_endpoint_requires_auth(client):
    res = client.get("/pets")
    assert res.status_code == 401


def test_pet_created_and_visible_only_to_its_owner(client):
    signup_res = client.post(
        "/auth/signup",
        json={"email": "petowner@example.com", "password": "hunter22pw", "privacy_policy_accepted": True},
    )
    headers = {"Authorization": f"Bearer {signup_res.json()['access_token']}"}

    create_res = client.post("/pets", json={"name": "Rex", "species": "dog"}, headers=headers)
    assert create_res.status_code == 200
    pet_id = create_res.json()["id"]

    list_res = client.get("/pets", headers=headers)
    assert any(p["id"] == pet_id for p in list_res.json())

    other_signup = client.post(
        "/auth/signup",
        json={"email": "someone-else@example.com", "password": "hunter22pw", "privacy_policy_accepted": True},
    )
    other_headers = {"Authorization": f"Bearer {other_signup.json()['access_token']}"}
    other_get = client.get(f"/pets/{pet_id}", headers=other_headers)
    assert other_get.status_code == 404  # exists, but not theirs — never confirmed as "exists"


def test_signup_rejects_short_password(client):
    res = client.post(
        "/auth/signup",
        json={"email": "short@example.com", "password": "short", "privacy_policy_accepted": True},
    )
    assert res.status_code == 422


def test_signup_requires_privacy_policy_acceptance(client):
    res = client.post(
        "/auth/signup",
        json={"email": "nopolicy@example.com", "password": "hunter22pw", "privacy_policy_accepted": False},
    )
    assert res.status_code == 422
```

```bash
pytest
```

---

## Verify

1. `pytest` green, including all six new auth tests alongside the existing triage/life-stage suites.
2. Sign up in the running app, confirm you land on the pet-profile screen (not the login screen).
3. Add a pet, log out, log back in — the pet is still there, tied to the account, not to a hardcoded demo owner.
4. Try `GET /pets/{some-other-account's-pet-id}` with your own token — confirm a 404, not the pet's data.
5. Hit `GET /auth/me/export` and `DELETE /auth/me` at least once manually — confirm export returns your pets and sessions, and delete actually removes the owner row plus every pet and triage session under it.

## What's still out of scope

Password reset/forgot-password flow, email verification, and refresh tokens (the JWT just expires after 7 days with no renewal) are all real gaps for a production launch, deliberately left out of this pass to get login shipped. Multi-pet UI (a pet switcher, since `list_my_pets` already returns all of them) and push notifications are the next two items from the original Phase 2 build guide.
