from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field as PydanticField, field_validator
from sqlalchemy import JSON, Column, Index, Enum as SAEnum
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
    consent_policy_version: Optional[str] = None
    email_verified_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Pet(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    owner_id: Optional[str] = Field(default=None, index=True, foreign_key="owner.id")
    name: str
    species: Species = Field(sa_type=SAEnum(Species, native_enum=False, length=4))
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = Field(default=None, sa_type=SAEnum(BreedSize, native_enum=False, length=6))
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = Field(default=None, sa_type=SAEnum(Sex, native_enum=False, length=6))
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    known_conditions: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class TriageSession(SQLModel, table=True):
    __table_args__ = (Index('ix_triagesession_pet_started_id', 'pet_id', 'started_at', 'id'),)
    id: str = Field(default_factory=_new_id, primary_key=True)
    pet_id: str = Field(index=True, foreign_key="pet.id")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symptom_entry_point: str
    answers_json: str = "{}"
    current_question_id: Optional[str] = None
    resulting_urgency: Optional[UrgencyLevel] = Field(default=None, sa_type=SAEnum(UrgencyLevel, native_enum=False, length=13))
    resulting_guidance: Optional[str] = None
    condition_entries_matched_raw: str = ""
    result_snapshot: Optional[dict] = Field(default=None, sa_column=Column(JSON(none_as_null=True), nullable=True))


class AuthSession(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    owner_id: str = Field(index=True, foreign_key="owner.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(index=True)
    authenticated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    revoked_at: Optional[datetime] = None


class AccountAction(SQLModel, table=True):
    token_hash: str = Field(primary_key=True)
    owner_id: str = Field(index=True, foreign_key="owner.id")
    kind: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(index=True)
    used_at: Optional[datetime] = None


class EmailDelivery(SQLModel, table=True):
    id: str = Field(default_factory=_new_id, primary_key=True)
    owner_id: str = Field(index=True, foreign_key="owner.id")
    encrypted_payload: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    next_attempt_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    attempts: int = 0


class GuestAccess(SQLModel, table=True):
    session_id: str = Field(primary_key=True, foreign_key="triagesession.id")
    token_hash: str
    expires_at: datetime = Field(index=True)


class MaintenanceStatus(SQLModel, table=True):
    job: str = Field(primary_key=True)
    last_success_at: datetime


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
    name: str = PydanticField(min_length=1, max_length=100)
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = PydanticField(default=None, gt=0, le=200, allow_inf_nan=False)
    environment_factors: list[EnvironmentFactor] = PydanticField(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("species")
    @classmethod
    def individual_species(cls, value: Species) -> Species:
        if value == Species.both:
            raise ValueError("Choose dog or cat for a pet")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def birth_date_not_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value


class TriageStartRequest(BaseModel):
    pet_id: Optional[str] = None
    symptom_tag: str = PydanticField(min_length=1, max_length=100)
    species: Species = Species.dog

    @field_validator("species")
    @classmethod
    def individual_species(cls, value: Species) -> Species:
        if value == Species.both:
            raise ValueError("Choose dog or cat for a check")
        return value


class TriageAnswerRequest(BaseModel):
    question_id: str
    answer: str


class ResultReason(BaseModel):
    kind: str
    detail: str
    urgency: UrgencyLevel


class RecordedAnswer(BaseModel):
    question_id: str
    prompt: str
    answer: str


class ReportPet(BaseModel):
    name: str
    species: Species
    date_of_birth: Optional[date] = None
    life_stage: Optional[str] = None
    sex: Optional[Sex] = None
    neutered: Optional[bool] = None
    breed_size: Optional[BreedSize] = None


class TriageResult(BaseModel):
    session_id: str
    resulting_urgency: UrgencyLevel
    resulting_guidance: str
    matched_condition_ids: list[str]
    possible_causes: list[str] = PydanticField(default_factory=list)
    recommended_examinations: list[str] = PydanticField(default_factory=list)
    reasons: list[ResultReason] = PydanticField(default_factory=list)
    answers: list[RecordedAnswer] = PydanticField(default_factory=list)
    pet: Optional[ReportPet] = None
    started_at: Optional[datetime] = None
    recorded_at: Optional[datetime] = None
    symptom: str = ""
    sources: list[str] = PydanticField(default_factory=list)
    content_version: Optional[str] = None
    historical: bool = False


class OwnerLogin(BaseModel):
    email: EmailStr
    password: str = PydanticField(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower() if isinstance(value, str) else value


class OwnerSignup(OwnerLogin):
    password: str = PydanticField(min_length=15, max_length=128)
    privacy_policy_accepted: bool

    @field_validator("privacy_policy_accepted")
    @classmethod
    def must_accept_privacy_policy(cls, value: bool) -> bool:
        if not value:
            raise ValueError("You must accept the privacy policy to create an account")
        return value


class OwnerPublic(BaseModel):
    id: str
    email: str
    created_at: datetime
    email_verified_at: Optional[datetime] = None
    email_verification_required: bool = False


class EmailRequest(BaseModel):
    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class ActionRequest(BaseModel):
    token: str = PydanticField(min_length=20, max_length=200)


class ResetPasswordRequest(ActionRequest):
    password: str = PydanticField(min_length=15, max_length=128)


class ReauthenticateRequest(BaseModel):
    password: str = PydanticField(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
