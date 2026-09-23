from datetime import date, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.content.loader import content_library
from app.models.schema import BreedSize, CatLifeStage, DogLifeStage, Pet, Sex, Species, TriageAnswerRequest, UrgencyLevel
from app.services.life_stage_calculator import calculate_cat_life_stage, calculate_dog_life_stage
from app.services import triage_engine


@pytest.fixture(scope="module", autouse=True)
def load_content():
    content_library.load()


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def dob_years_ago(years: float) -> date:
    return date.today() - timedelta(days=int(years * 365.25))


def make_pet(db, **overrides):
    values = {"owner_id": "owner-1", "name": "Test Pet", "species": Species.cat, "neutered": True, "sex": Sex.male}
    values.update(overrides)
    pet = Pet(**values)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def test_content_batch_validates():
    assert len(content_library.conditions) == 14
    assert len(content_library.preventive_items) == 4
    assert content_library.condition_by_id("dog-cat-parasite-001").urgency_default == UrgencyLevel.monitor_home
    assert len(content_library.questions_for_symptom("diarrhea")) == 2


def test_life_stage_boundaries():
    assert calculate_dog_life_stage(dob_years_ago(6.5), BreedSize.giant) == DogLifeStage.senior
    assert calculate_dog_life_stage(dob_years_ago(6.5), BreedSize.small) != DogLifeStage.senior
    assert calculate_cat_life_stage(dob_years_ago(11)) == CatLifeStage.senior


def test_urinary_blockage_is_emergency(db):
    pet = make_pet(db)
    session = triage_engine.start_session(db, pet, "straining_to_urinate")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-urinate-001", answer="None at all"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    assert "cat-urinary-001" in result.matched_condition_ids


def test_urgency_only_escalates(db):
    pet = make_pet(db, species=Species.dog)
    session = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="More than 3 times in a few hours"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_24h.rank
    assert result.matched_condition_ids == ["dog-gi-001"]


def test_species_scope_excludes_cat_hairball_guidance_for_dog(db):
    pet = make_pet(db, species=Species.dog)
    session = triage_engine.start_session(db, pet, "vomiting")
    result = triage_engine.compute_result(db, session.id)
    assert result.matched_condition_ids == ["dog-gi-001"]


def test_invalid_answer_is_rejected(db):
    pet = make_pet(db, species=Species.dog)
    session = triage_engine.start_session(db, pet, "vomiting")
    with pytest.raises(triage_engine.InvalidAnswerError):
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Maybe"))


@pytest.mark.parametrize(
    ("species", "symptom", "question_id", "answer", "expected"),
    [
        (Species.dog, "diarrhea", "q-diarrhea-001", "Yes, blood or black/tarry stool", UrgencyLevel.vet_24h),
        (Species.dog, "limping", "q-limping-002", "Yes", UrgencyLevel.emergency_now),
        (Species.dog, "reverse_sneezing", "q-reverse-sneezing-001", "Over a minute, or hasn't fully resolved", UrgencyLevel.vet_soon),
        (Species.cat, "scratching", "q-scratching-001", "Yes", UrgencyLevel.vet_soon),
    ],
)
def test_home_care_red_flags_escalate(db, species, symptom, question_id, answer, expected):
    pet = make_pet(db, species=species)
    session = triage_engine.start_session(db, pet, symptom)
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id=question_id, answer=answer))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == expected
