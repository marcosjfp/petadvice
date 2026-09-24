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
    session, first_question = triage_engine.start_session(db, pet, "straining_to_urinate")
    assert first_question.id == "q-urinate-001"
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-urinate-001", answer="None at all"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    assert "cat-urinary-001" in result.matched_condition_ids


def test_urgency_only_escalates(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="More than 3 times in a few hours"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No, neither"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_24h.rank
    assert result.matched_condition_ids == ["dog-gi-001"]


def test_species_scope_excludes_cat_hairball_guidance_for_dog(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    result = triage_engine.compute_result(db, session.id)
    assert result.matched_condition_ids == ["dog-gi-001"]


def test_invalid_answer_is_rejected(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
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
    session, _ = triage_engine.start_session(db, pet, symptom)
    if symptom == "limping":
        triage_engine.answer_question(
            db,
            session.id,
            TriageAnswerRequest(question_id="q-limping-001", answer="Yes, some weight-bearing"),
        )
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id=question_id, answer=answer))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == expected


def test_branching_flow_ends_immediately_on_emergency_answer(db):
    pet = make_pet(db, species=Species.dog)
    session, first_question = triage_engine.start_session(db, pet, "vomiting")
    assert first_question.id == "q-vomit-001"

    _, next_question, complete = triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once")
    )
    assert next_question.id == "q-vomit-002"
    assert complete is False

    _, next_question, complete = triage_engine.answer_question(
        db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="Yes")
    )
    assert next_question is None
    assert complete is True
    assert triage_engine.compute_result(db, session.id).resulting_urgency == UrgencyLevel.emergency_now


def test_result_surfaces_possible_causes_and_examinations(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No, neither"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-003", answer="No"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-004", answer="Normal energy and appetite"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.monitor_home
    assert result.possible_causes
    assert result.recommended_examinations


def test_puppy_vomiting_auto_escalates_via_life_stage(db):
    puppy = make_pet(
        db,
        species=Species.dog,
        date_of_birth=date.today() - timedelta(days=90),
        breed_size=BreedSize.medium,
    )
    session, _ = triage_engine.start_session(db, puppy, "vomiting")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="Once"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-002", answer="No, neither"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-003", answer="No"))
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-004", answer="Normal energy and appetite"))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_soon.rank
