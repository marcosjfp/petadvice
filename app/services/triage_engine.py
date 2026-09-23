import json

from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import ConditionEntry, NeuterStatus, Pet, TriageAnswerRequest, TriageResult, TriageSession, UrgencyLevel
from app.services.life_stage_calculator import calculate_life_stage


class UnknownSessionError(Exception):
    pass


class InvalidAnswerError(Exception):
    pass


def start_session(db: Session, pet: Pet, symptom_tag: str) -> TriageSession:
    session = TriageSession(pet_id=pet.id, symptom_entry_point=symptom_tag)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _pet_matches_condition_scope(pet: Pet, condition: ConditionEntry) -> bool:
    if condition.species not in (pet.species, condition.species.both):
        return False
    life_stage = calculate_life_stage(pet)
    if condition.applicable_life_stages and life_stage and life_stage not in condition.applicable_life_stages:
        return False
    if condition.applicable_sex and (pet.sex is None or pet.sex not in condition.applicable_sex):
        return False
    if condition.applicable_neuter_status:
        if pet.neutered is None:
            return False
        status = NeuterStatus.neutered if pet.neutered else NeuterStatus.intact
        if status not in condition.applicable_neuter_status:
            return False
    return True


def answer_question(db: Session, session_id: str, req: TriageAnswerRequest) -> TriageSession:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    question = next((item for item in content_library.questions_for_symptom(session.symptom_entry_point) if item.id == req.question_id), None)
    if question is None or req.answer not in question.options:
        raise InvalidAnswerError(req.question_id)
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
    if pet is None:
        raise UnknownSessionError(session.pet_id)

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    candidates = [condition for condition in matched if _pet_matches_condition_scope(pet, condition)]
    urgency = max((condition.urgency_default for condition in candidates), key=lambda item: item.rank, default=UrgencyLevel.monitor_home)
    answers = json.loads(session.answers_json)

    for question in content_library.questions_for_symptom(session.symptom_entry_point):
        answer = answers.get(question.id)
        if answer in question.escalate_if:
            urgency = max(urgency, question.escalate_if[answer], key=lambda item: item.rank)

    guidance = _build_guidance(urgency, candidates)
    session.resulting_urgency = urgency
    session.resulting_guidance = guidance
    session.condition_entries_matched_raw = ",".join(item.id for item in candidates)
    db.add(session)
    db.commit()
    return TriageResult(session_id=session.id, resulting_urgency=urgency, resulting_guidance=guidance, matched_condition_ids=[item.id for item in candidates])


def _build_guidance(urgency: UrgencyLevel, candidates: list[ConditionEntry]) -> str:
    if urgency == UrgencyLevel.monitor_home:
        texts = [item.home_care_guidance for item in candidates if item.home_care_guidance]
        return " ".join(texts) if texts else "Monitor your pet closely and contact a vet if things change or do not improve."
    if urgency == UrgencyLevel.vet_soon:
        return "Arrange a veterinary appointment within the next few days."
    if urgency == UrgencyLevel.vet_24h:
        return "Please arrange a veterinary appointment within 24 hours."
    return "This needs emergency veterinary attention now. Contact an emergency clinic immediately."
