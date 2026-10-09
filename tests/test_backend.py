from datetime import date, timedelta

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.content.loader import content_library
from app.models.schema import BreedSize, CatLifeStage, DogLifeStage, Pet, Sex, Species, TriageAnswerRequest, TriageSession, UrgencyLevel
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


def complete_remaining_questions(db, session_id):
    """Follow the normal-energy branch until every required question is answered."""
    while (question_id := db.get(TriageSession, session_id).current_question_id) is not None:
        question = content_library.question_by_id(question_id)
        triage_engine.answer_question(db, session_id, TriageAnswerRequest(
            question_id=question_id, answer=question.options[0],
        ))


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
    complete_remaining_questions(db, session.id)
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency.rank >= UrgencyLevel.vet_24h.rank
    assert result.matched_condition_ids == ["dog-gi-001"]


def test_species_scope_excludes_cat_hairball_guidance_for_dog(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "vomiting")
    complete_remaining_questions(db, session.id)
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
    complete_remaining_questions(db, session.id)
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


def test_incomplete_check_cannot_return_home_care(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    with pytest.raises(triage_engine.IncompleteSessionError):
        triage_engine.compute_result(db, session.id)


def test_completed_check_cannot_be_overwritten_or_accept_other_symptom(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, 'scratching')
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-scratching-001', answer='Yes'))
    for request in [
        TriageAnswerRequest(question_id='q-scratching-001', answer='No'),
        TriageAnswerRequest(question_id='q-vomit-001', answer='Once'),
    ]:
        with pytest.raises(triage_engine.InvalidAnswerError):
            triage_engine.answer_question(db, session.id, request)
    assert triage_engine.compute_result(db, session.id).resulting_urgency == UrgencyLevel.vet_soon


def test_unsupported_symptom_rejected(db):
    pet = make_pet(db)
    with pytest.raises(triage_engine.UnsupportedSymptomError):
        triage_engine.start_session(db, pet, 'not-a-symptom')


def test_no_applicable_content_never_returns_other_species_home_care(db):
    pet = make_pet(db, species=Species.cat)
    session, _ = triage_engine.start_session(db, pet, 'reverse_sneezing')
    complete_remaining_questions(db, session.id)
    result = triage_engine.compute_result(db, session.id)
    assert result.matched_condition_ids == []
    assert result.resulting_urgency == UrgencyLevel.vet_24h


def test_highest_applicable_urgency_wins(db):
    pet = make_pet(db, species=Species.dog, sex=Sex.female, neutered=False)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    complete_remaining_questions(db, session.id)
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    assert 'dog-cat-repro-001' in result.matched_condition_ids


@pytest.mark.parametrize('fault', ['duplicate', 'missing_branch', 'other_symptom', 'cycle', 'invalid_option', 'missing_entry'])
def test_invalid_question_graph_rejected(fault):
    from app.content.loader import ContentLibrary
    questions = [question.model_copy(deep=True) for question in content_library.questions]
    if fault == 'duplicate':
        questions.append(questions[0])
    elif fault == 'missing_branch':
        questions[0].next_question_by_answer['Once'] = 'missing'
    elif fault == 'other_symptom':
        questions[0].next_question_by_answer['Once'] = 'q-scratching-001'
    elif fault == 'cycle':
        questions[0].next_question_by_answer['Once'] = questions[0].id
    elif fault == 'invalid_option':
        questions[0].escalate_if['maybe'] = UrgencyLevel.emergency_now
    elif fault == 'missing_entry':
        questions[0].is_entry_point = False
    with pytest.raises(ValueError):
        ContentLibrary._validate_questions(questions)


def test_stale_request_cannot_overwrite_an_emergency_answer(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, 'vomiting')
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-001', answer='Once'))
    with Session(db.bind, expire_on_commit=False) as stale_db:
        stale_session = stale_db.get(TriageSession, session.id)
        assert stale_session.current_question_id == 'q-vomit-002'
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id='q-vomit-002', answer='Yes'))
        with pytest.raises(triage_engine.InvalidAnswerError):
            triage_engine.answer_question(stale_db, session.id, TriageAnswerRequest(question_id='q-vomit-002', answer='No, neither'))
    assert triage_engine.compute_result(db, session.id).resulting_urgency == UrgencyLevel.emergency_now
