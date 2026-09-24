from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field as PydanticField, field_validator
from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


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


class Owner(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    email: str = Field(index=True, unique=True)
    hashed_password: str
    consent_given_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Pet(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    owner_id: Optional[str] = Field(default=None, index=True, foreign_key="owner.id")
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
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symptom_entry_point: str
    answers_json: str = "{}"
    current_question_id: Optional[str] = None
    resulting_urgency: Optional[UrgencyLevel] = None
    resulting_guidance: Optional[str] = None
    condition_entries_matched_raw: str = ""


class RedFlag(BaseModel):
    description: str
    escalates_to: UrgencyLevel = UrgencyLevel.emergency_now


class ConditionEntry(BaseModel):
    id: str
    name: str
    species: Species
    category: Category
    applicable_life_stages: list[str] = PydanticField(default_factory=list)
    environment_factors: list[EnvironmentFactor] = PydanticField(default_factory=list)
    breed_predispositions: list[str] = PydanticField(default_factory=list)
    applicable_sex: list[Sex] = PydanticField(default_factory=list)
    applicable_neuter_status: list[NeuterStatus] = PydanticField(default_factory=list)
    symptom_tags: list[str]
    urgency_default: UrgencyLevel
    red_flags: list[RedFlag] = PydanticField(default_factory=list)
    life_stage_escalation: dict[str, UrgencyLevel] = PydanticField(default_factory=dict)
    home_care_guidance: Optional[str] = None
    prevention_tips: Optional[str] = None
    possible_causes: list[str] = PydanticField(default_factory=list)
    recommended_examinations: list[str] = PydanticField(default_factory=list)
    vet_reviewed_by: Optional[str] = None
    last_reviewed_date: Optional[date] = None
    sources: list[str] = PydanticField(default_factory=list)


class TriageQuestion(BaseModel):
    id: str
    prompt: str
    symptom_tag: str
    options: list[str]
    escalate_if: dict[str, UrgencyLevel] = PydanticField(default_factory=dict)
    is_entry_point: bool = False
    next_question_by_answer: dict[str, str] = PydanticField(default_factory=dict)


class PreventiveCareItem(BaseModel):
    id: str
    species: Species
    life_stage: str
    title: str
    description: str
    recurrence: Optional[str] = None
    trigger_age_days: Optional[int] = None
    sources: list[str] = PydanticField(default_factory=list)


class PetCreate(BaseModel):
    name: str
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[EnvironmentFactor] = PydanticField(default_factory=list)


class TriageStartRequest(BaseModel):
    pet_id: Optional[str] = None
    symptom_tag: str
    species: Species = Species.dog


class TriageAnswerRequest(BaseModel):
    question_id: str
    answer: str


class TriageResult(BaseModel):
    session_id: str
    resulting_urgency: UrgencyLevel
    resulting_guidance: str
    matched_condition_ids: list[str]
    possible_causes: list[str] = PydanticField(default_factory=list)
    recommended_examinations: list[str] = PydanticField(default_factory=list)


class OwnerSignup(BaseModel):
    email: str
    password: str
    privacy_policy_accepted: bool

    @field_validator("password")
    @classmethod
    def password_min_length(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value

    @field_validator("privacy_policy_accepted")
    @classmethod
    def must_accept_privacy_policy(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the privacy policy to create an account")
        return value


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
