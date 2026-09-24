# PETAdvice — Buddydoc-Depth Upgrade

> Adds: branching (adaptive) triage questions, two new reframed output fields (`possible_causes`, `recommended_examinations`), and automatic life-stage-based escalation that doesn't need a question at all. `vomiting` (`dog-gi-001`) is fully deepened as the template — repeat the pattern per symptom from here.
>
> **On the reframe:** `possible_causes` and `recommended_examinations` replace what Buddydoc calls "differential diagnoses." They must stay written as general categories of cause ("commonly associated with X, Y, Z"), never as an inference about the specific pet answering the questions ("your dog likely has X"). This distinction is what keeps the feature inside spec §2's legal guardrails — treat it as a hard content-authoring rule, same weight as the red-flags-need-vet-review rule.

---

## 1. Schema changes — replace `app/models/schema.py` with this

```python
# app/models/schema.py
"""
Core data models for PETAdvice.

Pet, Owner and TriageSession are SQLModel *table* models (persisted,
dynamic data). ConditionEntry, PreventiveCareItem and TriageQuestion
are plain Pydantic models loaded from versioned JSON content files —
see app/content/loader.py.
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
    neutered = "neutered"


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
    small = "small"
    medium = "medium"
    large = "large"
    giant = "giant"


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
    answers_json: str = "{}"
    current_question_id: Optional[str] = None  # NEW — tracks position in the branching flow
    resulting_urgency: Optional[UrgencyLevel] = None
    resulting_guidance: Optional[str] = None
    condition_entries_matched_raw: str = ""


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
    # NEW — automatic escalation from the pet's own computed life stage,
    # no question needed. e.g. {"puppy": "vet_soon", "senior": "vet_soon"}
    life_stage_escalation: dict[str, UrgencyLevel] = {}
    home_care_guidance: Optional[str] = None
    prevention_tips: Optional[str] = None
    # NEW — general educational categories of cause. NEVER phrase these as
    # an inference about the specific pet ("your pet has X") — that crosses
    # into diagnosis. "Commonly associated with X" is the correct register.
    possible_causes: list[str] = []
    # NEW — what a vet visit for this typically involves. Informational
    # ("your vet may check..."), not a personalized recommendation.
    recommended_examinations: list[str] = []
    vet_reviewed_by: Optional[str] = None
    last_reviewed_date: Optional[date] = None
    sources: list[str] = []


class TriageQuestion(BaseModel):
    id: str
    prompt: str
    symptom_tag: str
    options: list[str]
    escalate_if: dict[str, UrgencyLevel] = {}
    is_entry_point: bool = False  # NEW — marks the first question for a symptom_tag
    next_question_by_answer: dict[str, str] = {}  # NEW — answer -> next question id; absent = end of flow


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
    possible_causes: list[str] = []          # NEW
    recommended_examinations: list[str] = []  # NEW
```

---

## 2. Content loader — add a lookup method

In `app/content/loader.py`, add this method to `ContentLibrary` (alongside the existing `condition_by_id`) — everything else in that file (the multi-file glob loading from the previous batch) stays as-is:

```python
    def question_by_id(self, question_id: str) -> TriageQuestion | None:
        return next((q for q in self.questions if q.id == question_id), None)
```

---

## 3. Triage engine — replace `app/services/triage_engine.py` with this

```python
# app/services/triage_engine.py
"""
Branching (adaptive) triage flow. Per spec.md §6: urgency only ever
escalates, never de-escalates. A condition's red flags only apply if
the pet is in scope for that condition (right sex/neuter status), and
life-stage escalation now applies automatically from the pet's own
profile — no question needed for "is this a puppy?"
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
    TriageQuestion,
    TriageResult,
    TriageSession,
    UrgencyLevel,
)
from app.services.life_stage_calculator import calculate_life_stage


class UnknownSessionError(Exception):
    pass


def _entry_question(symptom_tag: str) -> TriageQuestion | None:
    candidates = content_library.questions_for_symptom(symptom_tag)
    entry = next((q for q in candidates if q.is_entry_point), None)
    return entry or (candidates[0] if candidates else None)


def _pet_matches_condition_scope(pet: Pet, condition: ConditionEntry) -> bool:
    if condition.applicable_sex and (pet.sex is None or pet.sex not in condition.applicable_sex):
        return False
    if condition.applicable_neuter_status:
        if pet.neutered is None:
            return False
        pet_status = NeuterStatus.neutered if pet.neutered else NeuterStatus.intact
        if pet_status not in condition.applicable_neuter_status:
            return False
    return True


def start_session(db: Session, pet: Pet, symptom_tag: str) -> tuple[TriageSession, TriageQuestion | None]:
    first_question = _entry_question(symptom_tag)
    session = TriageSession(
        pet_id=pet.id,
        symptom_entry_point=symptom_tag,
        current_question_id=first_question.id if first_question else None,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, first_question


def answer_question(
    db: Session, session_id: str, req: TriageAnswerRequest
) -> tuple[TriageSession, TriageQuestion | None, bool]:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)

    answers = json.loads(session.answers_json)
    answers[req.question_id] = req.answer
    session.answers_json = json.dumps(answers)

    answered_question = content_library.question_by_id(req.question_id)
    next_id = answered_question.next_question_by_answer.get(req.answer) if answered_question else None
    next_question = content_library.question_by_id(next_id) if next_id else None
    session.current_question_id = next_question.id if next_question else None
    flow_complete = next_question is None

    db.add(session)
    db.commit()
    db.refresh(session)
    return session, next_question, flow_complete


def compute_result(db: Session, session_id: str) -> TriageResult:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    pet = db.get(Pet, session.pet_id)
    pet_life_stage = calculate_life_stage(pet)

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    in_scope = [c for c in matched if _pet_matches_condition_scope(pet, c)]
    candidates = in_scope or matched

    urgency = (
        min((c.urgency_default for c in candidates), key=lambda u: u.rank)
        if candidates
        else UrgencyLevel.monitor_home
    )

    # 1) automatic escalation from the pet's own life stage — no question needed
    for c in candidates:
        if pet_life_stage and pet_life_stage in c.life_stage_escalation:
            candidate_level = c.life_stage_escalation[pet_life_stage]
            if candidate_level.rank > urgency.rank:
                urgency = candidate_level

    answers = json.loads(session.answers_json)

    # 2) escalate from answered questions (their own escalate_if, independent
    #    of which branch the answer sent the flow down)
    for q in content_library.questions_for_symptom(session.symptom_entry_point):
        given = answers.get(q.id)
        if given and given in q.escalate_if:
            candidate_level = q.escalate_if[given]
            if candidate_level.rank > urgency.rank:
                urgency = candidate_level

    # 3) escalate from in-scope conditions' red flags matching an answer
    #    (still a simple contains-match — same known MVP limitation as before)
    triggered_flags: list[RedFlag] = []
    for c in candidates:
        for flag in c.red_flags:
            for given in answers.values():
                if given.lower() in flag.description.lower():
                    triggered_flags.append(flag)
                    if flag.escalates_to.rank > urgency.rank:
                        urgency = flag.escalates_to

    guidance = _build_guidance(urgency, candidates)
    possible_causes = sorted({cause for c in candidates for cause in c.possible_causes})
    recommended_examinations = sorted({exam for c in candidates for exam in c.recommended_examinations})

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
        possible_causes=possible_causes,
        recommended_examinations=recommended_examinations,
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

---

## 4. API — replace `app/api/triage.py` with this

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
    """Full question set for a symptom — not used by the live branching
    flow (see /start and /answer below), kept for content review/debug
    tooling that wants to see the whole tree for a symptom at once."""
    return content_library.questions_for_symptom(symptom_tag)


@router.post("/start")
def start_triage(payload: TriageStartRequest, db: Session = Depends(get_session)):
    pet = db.get(Pet, payload.pet_id)
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    session, first_question = triage_engine.start_session(db, pet, payload.symptom_tag)
    return {
        "session_id": session.id,
        "next_question": first_question,
        "flow_complete": first_question is None,
    }


@router.post("/{session_id}/answer")
def answer_triage(session_id: str, payload: TriageAnswerRequest, db: Session = Depends(get_session)):
    try:
        _, next_question, flow_complete = triage_engine.answer_question(db, session_id, payload)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    return {"next_question": next_question, "flow_complete": flow_complete}


@router.get("/{session_id}/result")
def get_triage_result(session_id: str, db: Session = Depends(get_session)):
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
```

---

## 5. Content — replace `app/content/triage_questions.json` entirely

All existing symptom flows restructured into the branching format, plus the deepened 4-question `vomiting` flow (the template):

```json
[
  {
    "id": "q-vomit-001",
    "prompt": "How many times has your pet vomited?",
    "symptom_tag": "vomiting",
    "options": ["Once", "2-3 times", "More than 3 times in a few hours"],
    "escalate_if": { "More than 3 times in a few hours": "vet_24h" },
    "is_entry_point": true,
    "next_question_by_answer": {
      "Once": "q-vomit-002",
      "2-3 times": "q-vomit-002",
      "More than 3 times in a few hours": "q-vomit-002"
    }
  },
  {
    "id": "q-vomit-002",
    "prompt": "Is there blood in the vomit, or a swollen/bloated abdomen with unproductive retching (trying to vomit but nothing comes up)?",
    "symptom_tag": "vomiting",
    "options": ["No, neither", "Yes"],
    "escalate_if": { "Yes": "emergency_now" },
    "next_question_by_answer": { "No, neither": "q-vomit-003" }
  },
  {
    "id": "q-vomit-003",
    "prompt": "Any known or possible access to something toxic, a foreign object, or chocolate?",
    "symptom_tag": "vomiting",
    "options": ["No", "Yes, possible or known access"],
    "escalate_if": { "Yes, possible or known access": "vet_24h" },
    "next_question_by_answer": {
      "No": "q-vomit-004",
      "Yes, possible or known access": "q-vomit-004"
    }
  },
  {
    "id": "q-vomit-004",
    "prompt": "How is your pet's energy and appetite — any lethargy, or refusing food and water?",
    "symptom_tag": "vomiting",
    "options": ["Normal energy and appetite", "Lethargy, not eating, or not drinking"],
    "escalate_if": { "Lethargy, not eating, or not drinking": "vet_soon" },
    "next_question_by_answer": {}
  },
  {
    "id": "q-urinate-001",
    "prompt": "How much urine is being produced when straining?",
    "symptom_tag": "straining_to_urinate",
    "options": ["Normal amount", "A little", "None at all"],
    "escalate_if": { "A little": "emergency_now", "None at all": "emergency_now" },
    "is_entry_point": true,
    "next_question_by_answer": { "Normal amount": "q-urinate-002" }
  },
  {
    "id": "q-urinate-002",
    "prompt": "Is there any vomiting, lethargy, or collapse alongside this?",
    "symptom_tag": "straining_to_urinate",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "emergency_now" },
    "next_question_by_answer": {}
  },
  {
    "id": "q-diarrhea-001",
    "prompt": "Is there any blood in the stool, or is it black/tarry?",
    "symptom_tag": "diarrhea",
    "options": ["No", "Yes, blood or black/tarry stool"],
    "escalate_if": { "Yes, blood or black/tarry stool": "vet_24h" },
    "is_entry_point": true,
    "next_question_by_answer": {
      "No": "q-diarrhea-002",
      "Yes, blood or black/tarry stool": "q-diarrhea-002"
    }
  },
  {
    "id": "q-diarrhea-002",
    "prompt": "Is your pet also vomiting, lethargic, or refusing food and water?",
    "symptom_tag": "diarrhea",
    "options": ["No, otherwise normal", "Yes"],
    "escalate_if": { "Yes": "vet_24h" },
    "next_question_by_answer": {}
  },
  {
    "id": "q-limping-001",
    "prompt": "Is your dog putting any weight on the leg?",
    "symptom_tag": "limping",
    "options": ["Yes, some weight-bearing", "No weight-bearing at all"],
    "escalate_if": { "No weight-bearing at all": "vet_24h" },
    "is_entry_point": true,
    "next_question_by_answer": {
      "Yes, some weight-bearing": "q-limping-002",
      "No weight-bearing at all": "q-limping-002"
    }
  },
  {
    "id": "q-limping-002",
    "prompt": "Did this follow a fall, road accident, or other significant trauma?",
    "symptom_tag": "limping",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "emergency_now" },
    "next_question_by_answer": { "No": "q-limping-003" }
  },
  {
    "id": "q-limping-003",
    "prompt": "Any visible swelling, heat, wound, or pain when the leg is touched?",
    "symptom_tag": "limping",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "vet_24h" },
    "next_question_by_answer": {}
  },
  {
    "id": "q-reverse-sneezing-001",
    "prompt": "How long did the episode last, and did it fully resolve?",
    "symptom_tag": "reverse_sneezing",
    "options": ["Under a minute, back to normal", "Over a minute, or hasn't fully resolved"],
    "escalate_if": { "Over a minute, or hasn't fully resolved": "vet_soon" },
    "is_entry_point": true,
    "next_question_by_answer": {}
  },
  {
    "id": "q-scratching-001",
    "prompt": "Any pale gums, weakness, or lethargy alongside the itching?",
    "symptom_tag": "scratching",
    "options": ["No", "Yes"],
    "escalate_if": { "Yes": "vet_soon" },
    "is_entry_point": true,
    "next_question_by_answer": {}
  }
]
```

## 6. Content — deepen `dog-gi-001` in `petadvice-content-batch-homecare.json`

Replace that one entry (find it by `"id": "dog-gi-001"`) with this version. Note the old text red flag *"Puppy or senior dog..."* is gone — it's now handled automatically via `life_stage_escalation` instead of needing a question or a text-matched answer:

```json
{
  "id": "dog-gi-001",
  "name": "Acute vomiting, isolated episode",
  "species": "dog",
  "category": "gastrointestinal",
  "applicable_life_stages": ["puppy", "young_adult", "mature_adult", "senior"],
  "environment_factors": [],
  "breed_predispositions": [],
  "applicable_sex": [],
  "applicable_neuter_status": [],
  "symptom_tags": ["vomiting"],
  "urgency_default": "monitor_home",
  "life_stage_escalation": { "puppy": "vet_soon", "senior": "vet_soon" },
  "red_flags": [
    { "description": "Repeated vomiting, three or more times in a few hours", "escalates_to": "vet_24h" },
    { "description": "Blood in the vomit", "escalates_to": "emergency_now" },
    { "description": "Swollen or distended abdomen with unproductive retching", "escalates_to": "emergency_now" },
    { "description": "Known or suspected access to toxins, a foreign object, or chocolate", "escalates_to": "vet_24h" },
    { "description": "Vomiting alongside lethargy, not drinking, or refusing food beyond one missed meal", "escalates_to": "vet_soon" }
  ],
  "home_care_guidance": "For a single vomiting episode in an otherwise well adult dog: withhold food for a few hours (not water), then offer small, frequent amounts of a bland diet such as boiled chicken and white rice. Reintroduce normal food gradually over a few days once appetite and stools are back to normal.",
  "prevention_tips": "Secure bins and human food, and introduce new foods gradually over 7-10 days rather than all at once.",
  "possible_causes": [
    "Dietary indiscretion — scavenging, a sudden food change, or rich/fatty treats",
    "Mild gastritis",
    "Motion sickness",
    "Intestinal parasites",
    "Less commonly: obstruction, pancreatitis, or toxin ingestion — this is exactly what the red flags above are checking for"
  ],
  "recommended_examinations": [
    "A physical exam and abdominal palpation",
    "Bloodwork, if vomiting persists or your pet seems unwell, to check organ function and rule out other causes",
    "Abdominal X-rays or ultrasound, if a foreign object or obstruction is suspected",
    "Fecal testing, if parasites are a possibility"
  ],
  "vet_reviewed_by": null,
  "last_reviewed_date": null,
  "sources": [
    "https://appmgss.impactfirst.co/post/bland-diet-for-dogs",
    "https://petfolk.com/petfolklore/dog-diarrhea-causes-home-care-when-to-see-vet"
  ]
}
```

## 7. Frontend — replace `src/pages/TriageFlow.tsx` with this

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
  const [symptomTag, setSymptomTag] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null)
  const [result, setResult] = useState<any | null>(null)

  async function begin() {
    const res = (await api.startTriage(petId, symptomTag)) as any
    setSessionId(res.session_id)
    if (res.flow_complete) {
      setResult(await api.getTriageResult(res.session_id))
    } else {
      setCurrentQuestion(res.next_question)
    }
  }

  async function answer(option: string) {
    if (!sessionId || !currentQuestion) return
    const res = (await api.answerTriage(sessionId, currentQuestion.id, option)) as any
    if (res.flow_complete) {
      setResult(await api.getTriageResult(sessionId))
    } else {
      setCurrentQuestion(res.next_question)
    }
  }

  if (result) {
    return (
      <div className={`rounded-lg border-2 p-6 ${URGENCY_STYLES[result.resulting_urgency]}`}>
        <p className="text-sm font-semibold uppercase tracking-wide">
          {result.resulting_urgency.replace('_', ' ')}
        </p>
        <p className="mt-2">{result.resulting_guidance}</p>
        {result.possible_causes?.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-semibold">Commonly associated with:</p>
            <ul className="list-disc pl-5 text-sm">
              {result.possible_causes.map((c: string) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          </div>
        )}
        {result.recommended_examinations?.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-semibold">Your vet may want to check:</p>
            <ul className="list-disc pl-5 text-sm">
              {result.recommended_examinations.map((e: string) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          </div>
        )}
        <p className="mt-4 text-xs opacity-75">
          This is general guidance, not a diagnosis — always confirm with a vet.
        </p>
      </div>
    )
  }

  if (currentQuestion) {
    return (
      <div className="space-y-4">
        <p className="font-medium">{currentQuestion.prompt}</p>
        <div className="flex flex-wrap gap-2">
          {currentQuestion.options.map((opt) => (
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
        placeholder="Symptom tag, e.g. vomiting"
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

`api.getTriageQuestions` in `api/client.ts` is no longer called by this component (branching means the client only ever needs one question at a time) — leave the method in place, it's still useful for a future content-review screen.

---

## 8. Tests — add to `tests/test_triage_engine.py`

```python
from datetime import date, timedelta
from app.models.schema import BreedSize  # add to the existing import line if not already there


def test_branching_flow_ends_immediately_on_emergency_answer(db):
    pet = _make_pet(db, species=Species.dog, sex=Sex.male, neutered=True)
    session, first_q = triage_engine.start_session(db, pet, "vomiting")
    assert first_q.id == "q-vomit-001"

    _, next_q, complete = triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once")
    )
    assert next_q.id == "q-vomit-002"
    assert complete is False

    _, next_q2, complete2 = triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="Yes")
    )
    assert complete2 is True
    assert next_q2 is None

    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now


def test_result_surfaces_possible_causes_and_examinations(db):
    pet = _make_pet(db, species=Species.dog, sex=Sex.male, neutered=True)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No, neither"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-003", answer="No"))
    triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-004", answer="Normal energy and appetite")
    )
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
    assert len(result.possible_causes) > 0
    assert len(result.recommended_examinations) > 0


def test_puppy_vomiting_auto_escalates_via_life_stage_without_a_question(db):
    puppy_dob = date.today() - timedelta(days=90)  # 3 months old
    pet = _make_pet(
        db, species=Species.dog, sex=Sex.male, neutered=False,
        date_of_birth=puppy_dob, breed_size=BreedSize.medium,
    )
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No, neither"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-003", answer="No"))
    triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-004", answer="Normal energy and appetite")
    )
    result = triage_engine.compute_result(db, session.id)
    # every answer pointed to "fine" — the puppy life stage alone should
    # still push this to vet_soon, with no question ever asked about age
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_soon.rank
```

```bash
pytest
```

---

## Verify

1. `pytest` green, including the three new tests above.
2. Run the app, start a `vomiting` triage on a dog — confirm you get asked up to 4 questions (not a flat prefetched list), and that answering "Yes" to blood/bloating ends the flow immediately rather than continuing to ask irrelevant follow-ups.
3. Confirm the result screen now shows a "Commonly associated with" and "Your vet may want to check" section for vomiting — and confirm neither ever states a specific diagnosis for the pet.
4. Re-run the Phase 0 test (neutered male cat, `straining_to_urinate`, "None at all") — still `emergency_now`, unaffected by this change.

## Repeating this for the rest of the library

`vomiting` is now the reference pattern: 4-question branching tree, `life_stage_escalation` instead of an age question, `possible_causes` + `recommended_examinations` filled in and vet-reviewable alongside the existing fields. Apply the same treatment symptom-by-symptom — `diarrhea` and `limping` are the next-best candidates since they already have partial branching and just need `possible_causes`/`recommended_examinations` added to their `ConditionEntry`s to reach the same depth.
