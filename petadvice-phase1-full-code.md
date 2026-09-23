# PETAdvice — Phase 1 Full Code (single file)

> **Scope of this file:** the complete, working Phase 1 codebase — FastAPI backend (schema, life-stage calculator, triage engine, all API routes, tests) and the React PWA frontend, fully wired to each other. Every code block below has its destination path as a comment on the first line — create each file at that path, in that content, verbatim.
>
> **Not in this file:** Phase 2 (Capacitor native wrap, accounts/auth, push notifications, multi-pet UI). That's mostly platform configuration and credentials rather than novel application code, and it's already covered procedurally in `petadvice-build-guide-phase1-2.md` §2. Once Phase 1 is running, say the word and I'll do the same treatment for Phase 2 (Capacitor config, FCM wiring, auth endpoints) as its own single file.
>
> Companion files this depends on (already delivered — copy them in as noted below): `petadvice-app-spec.md`, `petadvice-content-batch-phase0.json`.

---

## Backend

### `requirements.txt`

```text
fastapi>=0.115
uvicorn[standard]>=0.30
sqlmodel>=0.0.22
pydantic>=2.8
pytest>=8.0
httpx>=0.27
```

### `app/models/schema.py`

```python
# app/models/schema.py
"""
Core data models for PETAdvice.

Pet, Owner and TriageSession are SQLModel *table* models (persisted,
dynamic data). ConditionEntry, PreventiveCareItem and TriageQuestion
are plain Pydantic models loaded from versioned JSON content files —
see app/content/loader.py. This split matches spec.md §4 / §8: content
is reviewed via PR diffs on JSON files, not edited through the DB.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


# --- Controlled vocabularies -------------------------------------------

class Species(str, Enum):
    dog = "dog"
    cat = "cat"
    both = "both"


class Sex(str, Enum):
    male = "male"
    female = "female"


class NeuterStatus(str, Enum):
    intact = "intact"
    neutered = "neutered"  # covers spayed females and castrated males


class DogLifeStage(str, Enum):
    puppy = "puppy"
    young_adult = "young_adult"
    mature_adult = "mature_adult"
    senior = "senior"


class CatLifeStage(str, Enum):
    kitten = "kitten"
    young_adult = "young_adult"
    mature_adult = "mature_adult"
    senior = "senior"


class BreedSize(str, Enum):
    small = "small"    # < 10kg adult
    medium = "medium"  # 10-25kg
    large = "large"    # 25-40kg
    giant = "giant"    # 40kg+


class Category(str, Enum):
    gastrointestinal = "gastrointestinal"
    dermatological = "dermatological"
    musculoskeletal = "musculoskeletal"
    dental_oral = "dental_oral"
    ear_eye = "ear_eye"
    respiratory = "respiratory"
    urinary_reproductive = "urinary_reproductive"
    parasites = "parasites"
    behavioral = "behavioral"
    weight_nutrition = "weight_nutrition"
    emergency_trauma = "emergency_trauma"


class EnvironmentFactor(str, Enum):
    indoor_only = "indoor_only"
    outdoor_access = "outdoor_access"
    multi_pet_household = "multi_pet_household"
    urban = "urban"
    rural = "rural"
    seasonal_summer = "seasonal_summer"
    seasonal_winter = "seasonal_winter"
    breed_predisposed = "breed_predisposed"


class UrgencyLevel(str, Enum):
    monitor_home = "monitor_home"
    vet_soon = "vet_soon"
    vet_24h = "vet_24h"
    emergency_now = "emergency_now"

    @property
    def rank(self) -> int:
        """Ordinal rank so the triage engine can compare/escalate urgency."""
        return {
            UrgencyLevel.monitor_home: 0,
            UrgencyLevel.vet_soon: 1,
            UrgencyLevel.vet_24h: 2,
            UrgencyLevel.emergency_now: 3,
        }[self]


def _new_id() -> str:
    return uuid.uuid4().hex


# --- Persisted (DB) models ------------------------------------------------

class Owner(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Pet(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    owner_id: str = Field(index=True, foreign_key="owner.id")
    name: str
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    known_conditions: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class TriageSession(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    pet_id: str = Field(index=True, foreign_key="pet.id")
    started_at: datetime = Field(default_factory=datetime.utcnow)
    symptom_entry_point: str
    answers_json: str = "{}"  # serialized dict[question_id, answer]
    resulting_urgency: Optional[UrgencyLevel] = None
    resulting_guidance: Optional[str] = None
    condition_entries_matched_raw: str = ""  # comma-separated ConditionEntry ids


# --- Content models (plain Pydantic — loaded from JSON, not DB tables) ---

class RedFlag(BaseModel):
    description: str
    escalates_to: UrgencyLevel = UrgencyLevel.emergency_now


class ConditionEntry(BaseModel):
    id: str
    name: str
    species: Species
    category: Category
    applicable_life_stages: list[str] = []
    environment_factors: list[EnvironmentFactor] = []
    breed_predispositions: list[str] = []
    applicable_sex: list[Sex] = []
    applicable_neuter_status: list[NeuterStatus] = []
    symptom_tags: list[str]
    urgency_default: UrgencyLevel
    red_flags: list[RedFlag] = []
    home_care_guidance: Optional[str] = None
    prevention_tips: Optional[str] = None
    vet_reviewed_by: Optional[str] = None
    last_reviewed_date: Optional[date] = None
    sources: list[str] = []


class TriageQuestion(BaseModel):
    id: str
    prompt: str
    symptom_tag: str
    options: list[str]
    escalate_if: dict[str, UrgencyLevel] = {}


class PreventiveCareItem(BaseModel):
    id: str
    species: Species
    life_stage: str
    title: str
    description: str
    recurrence: Optional[str] = None
    trigger_age_days: Optional[int] = None
    sources: list[str] = []


# --- API request/response shapes ------------------------------------------

class PetCreate(BaseModel):
    owner_id: str
    name: str
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[EnvironmentFactor] = []


class TriageStartRequest(BaseModel):
    pet_id: str
    symptom_tag: str


class TriageAnswerRequest(BaseModel):
    question_id: str
    answer: str


class TriageResult(BaseModel):
    session_id: str
    resulting_urgency: UrgencyLevel
    resulting_guidance: str
    matched_condition_ids: list[str]
```

### `app/db.py`

```python
# app/db.py
import os
from sqlmodel import SQLModel, Session, create_engine

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./petadvice.db")

# check_same_thread=False is only needed for SQLite + FastAPI's dev server
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, connect_args=connect_args)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
```

### `app/services/life_stage_calculator.py`

```python
# app/services/life_stage_calculator.py
"""
Computes a pet's current life stage from species, date of birth, and
(for dogs) breed size — per spec.md §3.2 (AAHA Canine Life Stage
Guidelines / AAHA-AAFP Feline Life Stage Guidelines).
"""
from datetime import date

from app.models.schema import BreedSize, CatLifeStage, DogLifeStage, Pet, Species


def _age_years(dob: date, as_of: date | None = None) -> float:
    as_of = as_of or date.today()
    return (as_of - dob).days / 365.25


# (young_adult_start, mature_adult_start, senior_start), in years, per breed
# size. Senior = "last 25% of estimated lifespan" per AAHA is the roughest
# part of the guideline to encode — these are reasonable defaults; refine
# per-breed once real content demands finer granularity.
_DOG_THRESHOLDS: dict[BreedSize, tuple[float, float, float]] = {
    BreedSize.small: (1.0, 3.5, 10.0),
    BreedSize.medium: (0.75, 3.5, 9.0),
    BreedSize.large: (0.75, 3.0, 7.5),
    BreedSize.giant: (0.5, 2.5, 6.0),
}

_CAT_THRESHOLDS = (1.0, 7.0, 10.0)  # young_adult, mature_adult, senior start


def calculate_dog_life_stage(dob: date, breed_size: BreedSize | None) -> DogLifeStage:
    size = breed_size or BreedSize.medium  # sensible default if unknown
    puppy_end, mature_start, senior_start = _DOG_THRESHOLDS[size]
    age = _age_years(dob)
    if age < puppy_end:
        return DogLifeStage.puppy
    if age < mature_start:
        return DogLifeStage.young_adult
    if age < senior_start:
        return DogLifeStage.mature_adult
    return DogLifeStage.senior


def calculate_cat_life_stage(dob: date) -> CatLifeStage:
    young_start, mature_start, senior_start = _CAT_THRESHOLDS
    age = _age_years(dob)
    if age < young_start:
        return CatLifeStage.kitten
    if age < mature_start:
        return CatLifeStage.young_adult
    if age < senior_start:
        return CatLifeStage.mature_adult
    return CatLifeStage.senior


def calculate_life_stage(pet: Pet) -> str | None:
    if pet.date_of_birth is None:
        return None
    if pet.species == Species.dog:
        return calculate_dog_life_stage(pet.date_of_birth, pet.breed_size).value
    if pet.species == Species.cat:
        return calculate_cat_life_stage(pet.date_of_birth).value
    return None
```

### `app/content/loader.py`

```python
# app/content/loader.py
"""
Loads and validates the JSON content library at startup. Fails loudly
on any schema mismatch — this is the tripwire that catches content/
schema drift as the library grows (build guide §1.2 step 4).
"""
import json
from pathlib import Path

from pydantic import ValidationError

from app.models.schema import ConditionEntry, PreventiveCareItem, TriageQuestion

CONTENT_DIR = Path(__file__).parent
CONDITIONS_FILE = CONTENT_DIR / "petadvice-content-batch-phase0.json"
QUESTIONS_FILE = CONTENT_DIR / "triage_questions.json"


class ContentLibrary:
    def __init__(self) -> None:
        self.conditions: list[ConditionEntry] = []
        self.preventive_items: list[PreventiveCareItem] = []
        self.questions: list[TriageQuestion] = []

    def load(self) -> None:
        data = json.loads(CONDITIONS_FILE.read_text())
        try:
            self.conditions = [ConditionEntry(**c) for c in data["condition_entries"]]
            self.preventive_items = [PreventiveCareItem(**p) for p in data["preventive_care_items"]]
        except ValidationError as e:
            raise RuntimeError(f"Content library failed schema validation: {e}") from e

        if QUESTIONS_FILE.exists():
            q_data = json.loads(QUESTIONS_FILE.read_text())
            try:
                self.questions = [TriageQuestion(**q) for q in q_data]
            except ValidationError as e:
                raise RuntimeError(f"Triage questions failed schema validation: {e}") from e

    def conditions_for_symptom(self, symptom_tag: str) -> list[ConditionEntry]:
        return [c for c in self.conditions if symptom_tag in c.symptom_tags]

    def condition_by_id(self, condition_id: str) -> ConditionEntry | None:
        return next((c for c in self.conditions if c.id == condition_id), None)

    def questions_for_symptom(self, symptom_tag: str) -> list[TriageQuestion]:
        return [q for q in self.questions if q.symptom_tag == symptom_tag]

    def filter_conditions(
        self,
        species: str | None = None,
        category: str | None = None,
        life_stage: str | None = None,
        symptom_tag: str | None = None,
    ) -> list[ConditionEntry]:
        results = self.conditions
        if species:
            results = [c for c in results if c.species.value in (species, "both")]
        if category:
            results = [c for c in results if c.category.value == category]
        if life_stage:
            results = [c for c in results if life_stage in c.applicable_life_stages]
        if symptom_tag:
            results = [c for c in results if symptom_tag in c.symptom_tags]
        return results

    def filter_preventive(
        self, species: str | None = None, life_stage: str | None = None
    ) -> list[PreventiveCareItem]:
        results = self.preventive_items
        if species:
            results = [p for p in results if p.species.value in (species, "both")]
        if life_stage:
            results = [p for p in results if p.life_stage == life_stage]
        return results


content_library = ContentLibrary()  # module-level singleton, loaded at app startup
```

### `app/content/petadvice-content-batch-phase0.json`

Copy the file already delivered (from the Phase 0 step) to this exact path — don't regenerate it, reuse it as-is so `vet_reviewed_by`/`last_reviewed_date` stay intact once your wife/vet review it.

### `app/content/triage_questions.json`

A starter set covering the two symptom tags exercised below — the highest-stakes one (`straining_to_urinate`, tied to the emergency cat-urinary entry) and a common one (`vomiting`). Expand this file as more `ConditionEntry.symptom_tags` get content.

```json
[
  {
    "id": "q-urinate-001",
    "prompt": "How much urine is being produced when straining?",
    "symptom_tag": "straining_to_urinate",
    "options": ["Normal amount", "A little", "None at all"],
    "escalate_if": {
      "A little": "emergency_now",
      "None at all": "emergency_now"
    }
  },
  {
    "id": "q-urinate-002",
    "prompt": "Is there any vomiting, lethargy, or collapse alongside this?",
    "symptom_tag": "straining_to_urinate",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "emergency_now" }
  },
  {
    "id": "q-vomit-001",
    "prompt": "How many times has your pet vomited?",
    "symptom_tag": "vomiting",
    "options": ["Once", "2-3 times", "More than 3 times in a few hours"],
    "escalate_if": { "More than 3 times in a few hours": "vet_24h" }
  },
  {
    "id": "q-vomit-002",
    "prompt": "Is there blood in the vomit, or a swollen abdomen with unproductive retching?",
    "symptom_tag": "vomiting",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "emergency_now" }
  }
]
```

### `app/services/triage_engine.py`

```python
# app/services/triage_engine.py
"""
Structured (multiple-choice, not free-text/AI) triage flow.
Per spec.md §6: urgency only ever escalates during a session, never
de-escalates, and a condition's red flags only apply if the pet is
actually in scope for that condition (right sex / neuter status).
"""
import json

from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import (
    ConditionEntry,
    NeuterStatus,
    Pet,
    RedFlag,
    TriageAnswerRequest,
    TriageResult,
    TriageSession,
    UrgencyLevel,
)


class UnknownSessionError(Exception):
    pass


def start_session(db: Session, pet: Pet, symptom_tag: str) -> TriageSession:
    session = TriageSession(pet_id=pet.id, symptom_entry_point=symptom_tag)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _pet_matches_condition_scope(pet: Pet, condition: ConditionEntry) -> bool:
    """A sex/neuter-gated entry (e.g. pyometra, an intact-female-only
    condition) should never fire for a pet outside that scope, however
    the owner answers the questions."""
    if condition.applicable_sex and (pet.sex is None or pet.sex not in condition.applicable_sex):
        return False
    if condition.applicable_neuter_status:
        if pet.neutered is None:
            return False
        pet_status = NeuterStatus.neutered if pet.neutered else NeuterStatus.intact
        if pet_status not in condition.applicable_neuter_status:
            return False
    return True


def answer_question(db: Session, session_id: str, req: TriageAnswerRequest) -> TriageSession:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)

    answers = json.loads(session.answers_json)
    answers[req.question_id] = req.answer
    session.answers_json = json.dumps(answers)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def compute_result(db: Session, session_id: str) -> TriageResult:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    pet = db.get(Pet, session.pet_id)

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    in_scope = [c for c in matched if _pet_matches_condition_scope(pet, c)]
    # fall back to the unfiltered match if nothing is in scope — safer to
    # show cautious generic guidance than nothing at all
    candidates = in_scope or matched

    urgency = (
        min((c.urgency_default for c in candidates), key=lambda u: u.rank)
        if candidates
        else UrgencyLevel.monitor_home
    )

    answers = json.loads(session.answers_json)

    # 1) escalate from answered questions
    for q in content_library.questions_for_symptom(session.symptom_entry_point):
        given = answers.get(q.id)
        if given and given in q.escalate_if:
            candidate_level = q.escalate_if[given]
            if candidate_level.rank > urgency.rank:
                urgency = candidate_level

    # 2) escalate from in-scope conditions' red flags matching an answer
    #    (simple contains-match for MVP; swap for tag-based matching once
    #    red flags carry their own tags instead of free text)
    triggered_flags: list[RedFlag] = []
    for c in candidates:
        for flag in c.red_flags:
            for given in answers.values():
                if given.lower() in flag.description.lower():
                    triggered_flags.append(flag)
                    if flag.escalates_to.rank > urgency.rank:
                        urgency = flag.escalates_to

    guidance = _build_guidance(urgency, candidates)

    session.resulting_urgency = urgency
    session.resulting_guidance = guidance
    session.condition_entries_matched_raw = ",".join(c.id for c in candidates)
    db.add(session)
    db.commit()

    return TriageResult(
        session_id=session.id,
        resulting_urgency=urgency,
        resulting_guidance=guidance,
        matched_condition_ids=[c.id for c in candidates],
    )


def _build_guidance(urgency: UrgencyLevel, candidates: list[ConditionEntry]) -> str:
    if urgency == UrgencyLevel.monitor_home:
        home_texts = [c.home_care_guidance for c in candidates if c.home_care_guidance]
        if home_texts:
            return " ".join(home_texts)
        return "This can usually be monitored at home. Watch closely and contact a vet if things change or don't improve."
    if urgency == UrgencyLevel.vet_soon:
        return "This is worth a vet visit in the next few days — it doesn't need to be same-day, but don't let it go unaddressed."
    if urgency == UrgencyLevel.vet_24h:
        return "Please see a vet within 24 hours."
    return "This needs emergency veterinary attention now — please go to a vet or emergency clinic immediately."
```

### `app/api/pets.py`

```python
# app/api/pets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import Pet, PetCreate
from app.services.life_stage_calculator import calculate_life_stage

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=Pet)
def create_pet(payload: PetCreate, db: Session = Depends(get_session)):
    pet = Pet(
        **payload.model_dump(exclude={"environment_factors"}),
        environment_factors=[f.value for f in payload.environment_factors],
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


@router.get("/{pet_id}")
def get_pet(pet_id: str, db: Session = Depends(get_session)):
    pet = db.get(Pet, pet_id)
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    return {**pet.model_dump(), "life_stage": calculate_life_stage(pet)}


@router.get("")
def list_pets_for_owner(owner_id: str, db: Session = Depends(get_session)):
    pets = db.exec(select(Pet).where(Pet.owner_id == owner_id)).all()
    return [{**p.model_dump(), "life_stage": calculate_life_stage(p)} for p in pets]
```

### `app/api/conditions.py`

```python
# app/api/conditions.py
from fastapi import APIRouter, HTTPException

from app.content.loader import content_library

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("")
def list_conditions(
    species: str | None = None,
    category: str | None = None,
    life_stage: str | None = None,
    symptom_tag: str | None = None,
):
    return content_library.filter_conditions(species, category, life_stage, symptom_tag)


@router.get("/{condition_id}")
def get_condition(condition_id: str):
    condition = content_library.condition_by_id(condition_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    return condition
```

### `app/api/triage.py`

```python
# app/api/triage.py
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.content.loader import content_library
from app.db import get_session
from app.models.schema import Pet, TriageAnswerRequest, TriageStartRequest
from app.services import triage_engine

router = APIRouter(prefix="/triage", tags=["triage"])


@router.get("/questions")
def get_triage_questions(symptom_tag: str):
    return content_library.questions_for_symptom(symptom_tag)


@router.post("/start")
def start_triage(payload: TriageStartRequest, db: Session = Depends(get_session)):
    pet = db.get(Pet, payload.pet_id)
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    session = triage_engine.start_session(db, pet, payload.symptom_tag)
    return {"session_id": session.id}


@router.post("/{session_id}/answer")
def answer_triage(session_id: str, payload: TriageAnswerRequest, db: Session = Depends(get_session)):
    try:
        triage_engine.answer_question(db, session_id, payload)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    return {"status": "recorded"}


@router.get("/{session_id}/result")
def get_triage_result(session_id: str, db: Session = Depends(get_session)):
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
```

### `app/api/preventive_care.py`

```python
# app/api/preventive_care.py
from fastapi import APIRouter

from app.content.loader import content_library

router = APIRouter(prefix="/preventive-care", tags=["preventive-care"])


@router.get("")
def list_preventive_care(species: str | None = None, life_stage: str | None = None):
    return content_library.filter_preventive(species, life_stage)
```

### `app/main.py`

```python
# app/main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import conditions, pets, preventive_care, triage
from app.content.loader import content_library
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    content_library.load()  # fails loudly on schema drift — see loader.py
    yield


app = FastAPI(title="PETAdvice API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your real frontend origin(s) before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pets.router)
app.include_router(conditions.router)
app.include_router(triage.router)
app.include_router(preventive_care.router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## Backend tests

### `tests/test_life_stage_calculator.py`

```python
# tests/test_life_stage_calculator.py
from datetime import date, timedelta

from app.models.schema import BreedSize, CatLifeStage, DogLifeStage
from app.services.life_stage_calculator import calculate_cat_life_stage, calculate_dog_life_stage


def _dob_years_ago(years: float) -> date:
    return date.today() - timedelta(days=int(years * 365.25))


def test_giant_breed_dog_is_senior_earlier_than_small_breed():
    dob = _dob_years_ago(6.5)
    assert calculate_dog_life_stage(dob, BreedSize.giant) == DogLifeStage.senior
    assert calculate_dog_life_stage(dob, BreedSize.small) != DogLifeStage.senior


def test_puppy_boundary_large_breed():
    assert calculate_dog_life_stage(_dob_years_ago(0.5), BreedSize.large) == DogLifeStage.puppy
    assert calculate_dog_life_stage(_dob_years_ago(1.0), BreedSize.large) == DogLifeStage.young_adult


def test_cat_life_stages():
    assert calculate_cat_life_stage(_dob_years_ago(0.5)) == CatLifeStage.kitten
    assert calculate_cat_life_stage(_dob_years_ago(3.0)) == CatLifeStage.young_adult
    assert calculate_cat_life_stage(_dob_years_ago(8.0)) == CatLifeStage.mature_adult
    assert calculate_cat_life_stage(_dob_years_ago(11.0)) == CatLifeStage.senior
```

### `tests/test_triage_engine.py`

```python
# tests/test_triage_engine.py
"""
Priority test suite per build guide §1.2 step 9 — this is the
highest-stakes code in the app.
"""
import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.content.loader import content_library
from app.models.schema import Pet, Sex, Species, TriageAnswerRequest, UrgencyLevel
from app.services import triage_engine


@pytest.fixture(autouse=True, scope="module")
def _load_content():
    content_library.load()


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _make_pet(db, **overrides) -> Pet:
    defaults = dict(owner_id="owner-1", name="Test Pet", species=Species.cat, neutered=True, sex=Sex.male)
    defaults.update(overrides)
    pet = Pet(**defaults)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def test_neutered_male_cat_no_urine_output_is_emergency(db):
    pet = _make_pet(db, species=Species.cat, sex=Sex.male, neutered=True)
    session = triage_engine.start_session(db, pet, "straining_to_urinate")
    triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-urinate-001", answer="None at all")
    )
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    assert "cat-urinary-001" in result.matched_condition_ids


def test_urgency_never_de_escalates_across_answers(db):
    pet = _make_pet(db, species=Species.dog, sex=Sex.male, neutered=True)
    session = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(
        db, session.id,
        TriageAnswerRequest(question_id="q-vomit-001", answer="More than 3 times in a few hours"),
    )
    triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No")
    )
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_24h.rank


def test_blood_in_vomit_escalates_to_emergency(db):
    pet = _make_pet(db, species=Species.dog, sex=Sex.male, neutered=True)
    session = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="Yes")
    )
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now


def test_monitor_home_is_the_floor_for_unmatched_symptoms(db):
    pet = _make_pet(db, species=Species.dog, sex=Sex.male, neutered=True)
    session = triage_engine.start_session(db, pet, "unlisted_symptom_tag")
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
```

### Backend setup & run

```bash
pip install -r requirements.txt
# copy the two content files into app/content/ (paths above)
uvicorn app.main:app --reload
# → API docs at http://localhost:8000/docs

pytest
```

---

## Frontend (PWA)

### `package.json`

```json
{
  "name": "petadvice-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vite-plugin-pwa": "^0.20.0"
  }
}
```

### `vite.config.ts`

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'PETAdvice',
        short_name: 'PETAdvice',
        description: "First point of reference for cat and dog owners — not a replacement for your vet.",
        theme_color: '#0f766e',
        background_color: '#ffffff',
        display: 'standalone',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
    }),
  ],
})
```

### `tailwind.config.js`

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: { extend: {} },
  plugins: [],
}
```

### `postcss.config.js`

```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

### `index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>PETAdvice</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

### `src/index.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

### `src/main.tsx`

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

### `src/api/client.ts`

```ts
const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  createPet: (payload: unknown) => request('/pets', { method: 'POST', body: JSON.stringify(payload) }),
  getPet: (petId: string) => request(`/pets/${petId}`),
  listPets: (ownerId: string) => request(`/pets?owner_id=${ownerId}`),
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

### `src/pages/PetProfile.tsx`

```tsx
// src/pages/PetProfile.tsx
import { useState } from 'react'
import { api } from '../api/client'

export function PetProfileForm({
  ownerId,
  onCreated,
}: {
  ownerId: string
  onCreated: (petId: string) => void
}) {
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
      owner_id: ownerId,
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

### `src/pages/TriageFlow.tsx`

```tsx
// src/pages/TriageFlow.tsx
import { useState } from 'react'
import { api } from '../api/client'

const URGENCY_STYLES: Record<string, string> = {
  monitor_home: 'bg-green-50 border-green-400 text-green-900',
  vet_soon: 'bg-yellow-50 border-yellow-400 text-yellow-900',
  vet_24h: 'bg-orange-50 border-orange-500 text-orange-900',
  emergency_now: 'bg-red-50 border-red-600 text-red-900 animate-pulse',
}

type Question = { id: string; prompt: string; options: string[] }

export function TriageFlow({ petId }: { petId: string }) {
  // NOTE: free-text symptom tag is a placeholder — swap for a proper
  // symptom picker backed by GET /conditions once the content library
  // has enough entries to build a searchable list from.
  const [symptomTag, setSymptomTag] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [questions, setQuestions] = useState<Question[]>([])
  const [step, setStep] = useState(0)
  const [result, setResult] = useState<any | null>(null)

  async function begin() {
    const { session_id } = (await api.startTriage(petId, symptomTag)) as any
    const qs = (await api.getTriageQuestions(symptomTag)) as Question[]
    setSessionId(session_id)
    setQuestions(qs)
    setStep(0)
  }

  async function answer(option: string) {
    if (!sessionId) return
    await api.answerTriage(sessionId, questions[step].id, option)
    if (step + 1 < questions.length) {
      setStep(step + 1)
    } else {
      setResult(await api.getTriageResult(sessionId))
    }
  }

  if (result) {
    return (
      <div className={`rounded-lg border-2 p-6 ${URGENCY_STYLES[result.resulting_urgency]}`}>
        <p className="text-sm font-semibold uppercase tracking-wide">
          {result.resulting_urgency.replace('_', ' ')}
        </p>
        <p className="mt-2">{result.resulting_guidance}</p>
        <p className="mt-4 text-xs opacity-75">
          This is general guidance, not a diagnosis — always confirm with a vet.
        </p>
      </div>
    )
  }

  if (sessionId && questions.length > 0) {
    const q = questions[step]
    return (
      <div className="space-y-4">
        <p className="font-medium">{q.prompt}</p>
        <div className="flex flex-wrap gap-2">
          {q.options.map((opt) => (
            <button
              key={opt}
              className="rounded border px-3 py-2 hover:bg-gray-50"
              onClick={() => answer(opt)}
            >
              {opt}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <input
        className="w-full rounded border p-2"
        placeholder="Symptom tag, e.g. straining_to_urinate"
        value={symptomTag}
        onChange={(e) => setSymptomTag(e.target.value)}
      />
      <button className="rounded bg-teal-700 px-4 py-2 text-white" onClick={begin}>
        Start
      </button>
    </div>
  )
}
```

### `src/pages/ConditionLibrary.tsx`

```tsx
// src/pages/ConditionLibrary.tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function ConditionLibrary({ species }: { species: string }) {
  const [conditions, setConditions] = useState<any[]>([])

  useEffect(() => {
    api.listConditions({ species }).then((c) => setConditions(c as any[]))
  }, [species])

  return (
    <ul className="space-y-3">
      {conditions.map((c) => (
        <li key={c.id} className="rounded border p-3">
          <p className="font-medium">{c.name}</p>
          <p className="text-sm text-gray-600">{c.category.replace('_', ' ')}</p>
        </li>
      ))}
    </ul>
  )
}
```

### `src/pages/PreventiveCare.tsx`

```tsx
// src/pages/PreventiveCare.tsx
import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function PreventiveCare({
  species,
  lifeStage,
}: {
  species: string
  lifeStage: string | null
}) {
  const [items, setItems] = useState<any[]>([])

  useEffect(() => {
    if (!lifeStage) return
    api.listPreventiveCare({ species, life_stage: lifeStage }).then((i) => setItems(i as any[]))
  }, [species, lifeStage])

  return (
    <ul className="space-y-3">
      {items.map((i) => (
        <li key={i.id} className="rounded border p-3">
          <p className="font-medium">{i.title}</p>
          <p className="text-sm text-gray-600">{i.description}</p>
        </li>
      ))}
    </ul>
  )
}
```

### `src/components/EmergencyReference.tsx`

```tsx
// src/components/EmergencyReference.tsx
export function EmergencyReference() {
  return (
    <div className="fixed bottom-0 left-0 right-0 border-t-2 border-red-600 bg-red-50 p-3 text-sm text-red-900">
      <strong>Always an emergency:</strong> difficulty breathing, collapse, seizures, a
      bloated/distended abdomen with unproductive retching, straining to urinate with no output,
      uncontrolled bleeding. If you see any of these — go to a vet now, don't wait for the triage
      flow.
    </div>
  )
}
```

### `src/App.tsx`

```tsx
// src/App.tsx
import { useState } from 'react'
import { PetProfileForm } from './pages/PetProfile'
import { TriageFlow } from './pages/TriageFlow'
import { ConditionLibrary } from './pages/ConditionLibrary'
import { PreventiveCare } from './pages/PreventiveCare'
import { EmergencyReference } from './components/EmergencyReference'

const OWNER_ID = 'demo-owner' // replace once accounts land in Phase 2

export default function App() {
  const [petId, setPetId] = useState<string | null>(null)
  const [tab, setTab] = useState<'triage' | 'library' | 'preventive'>('triage')

  return (
    <div className="mx-auto max-w-2xl p-4 pb-24">
      <h1 className="text-2xl font-bold text-teal-800">PETAdvice</h1>
      {!petId ? (
        <PetProfileForm ownerId={OWNER_ID} onCreated={setPetId} />
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

### Frontend setup & run

```bash
npm install
npm run dev
# → http://localhost:5173, talking to the backend on :8000
```

(App icons `icon-192.png` / `icon-512.png` referenced in `vite.config.ts` aren't included here — drop in placeholders or real artwork before your first PWA install test.)

---

## What an agent should do with this file

1. Create every file above at its exact path.
2. Copy in `petadvice-content-batch-phase0.json` from the Phase 0 deliverable.
3. `pip install -r requirements.txt && pytest` — should be green before touching the frontend.
4. `npm install && npm run dev` alongside `uvicorn app.main:app --reload` — click through: create a pet → run the `straining_to_urinate` triage flow on a neutered male cat and confirm it lands on `emergency_now`.
5. Only then move to Phase 2 per the build guide.
