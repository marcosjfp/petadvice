import json

from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import ConditionEntry, NeuterStatus, Pet, RedFlag, TriageAnswerRequest, TriageQuestion, TriageResult, TriageSession, UrgencyLevel
from app.services.life_stage_calculator import calculate_life_stage


class UnknownSessionError(Exception):
    pass


class InvalidAnswerError(Exception):
    pass


def _entry_question(symptom_tag: str) -> TriageQuestion | None:
    questions = content_library.questions_for_symptom(symptom_tag)
    return next((question for question in questions if question.is_entry_point), questions[0] if questions else None)


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


def answer_question(db: Session, session_id: str, req: TriageAnswerRequest) -> tuple[TriageSession, TriageQuestion | None, bool]:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    question = content_library.question_by_id(req.question_id)
    if question is None or req.answer not in question.options:
        raise InvalidAnswerError(req.question_id)
    if session.current_question_id and session.current_question_id != req.question_id:
        raise InvalidAnswerError(req.question_id)
    answers = json.loads(session.answers_json)
    answers[req.question_id] = req.answer
    session.answers_json = json.dumps(answers)
    next_id = question.next_question_by_answer.get(req.answer)
    next_question = content_library.question_by_id(next_id) if next_id else None
    session.current_question_id = next_question.id if next_question else None
    db.add(session)
    db.commit()
    db.refresh(session)
    return session, next_question, next_question is None


def compute_result(db: Session, session_id: str) -> TriageResult:
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    pet = db.get(Pet, session.pet_id)
    if pet is None:
        raise UnknownSessionError(session.pet_id)

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    candidates = [condition for condition in matched if _pet_matches_condition_scope(pet, condition)]
    candidates = candidates or matched
    urgency = min((condition.urgency_default for condition in candidates), key=lambda item: item.rank, default=UrgencyLevel.monitor_home)
    life_stage = calculate_life_stage(pet)
    for condition in candidates:
        escalation = condition.life_stage_escalation.get(life_stage) if life_stage else None
        if escalation and escalation.rank > urgency.rank:
            urgency = escalation
    answers = json.loads(session.answers_json)

    for question in content_library.questions_for_symptom(session.symptom_entry_point):
        answer = answers.get(question.id)
        if answer in question.escalate_if:
            escalation = question.escalate_if[answer]
            if escalation.rank > urgency.rank:
                urgency = escalation

    triggered_flags: list[RedFlag] = []
    for condition in candidates:
        for flag in condition.red_flags:
            if any(
                len(answer.strip()) > 2 and answer.lower() in flag.description.lower()
                for answer in answers.values()
            ):
                triggered_flags.append(flag)
                if flag.escalates_to.rank > urgency.rank:
                    urgency = flag.escalates_to

    guidance = _build_guidance(urgency, candidates)
    session.resulting_urgency = urgency
    session.resulting_guidance = guidance
    session.condition_entries_matched_raw = ",".join(item.id for item in candidates)
    db.add(session)
    db.commit()
    return TriageResult(
        session_id=session.id,
        resulting_urgency=urgency,
        resulting_guidance=guidance,
        matched_condition_ids=[item.id for item in candidates],
        possible_causes=sorted({cause for condition in candidates for cause in condition.possible_causes}),
        recommended_examinations=sorted({exam for condition in candidates for exam in condition.recommended_examinations}),
    )


def _build_guidance(urgency: UrgencyLevel, candidates: list[ConditionEntry]) -> str:
    if urgency == UrgencyLevel.monitor_home:
        texts = [item.home_care_guidance for item in candidates if item.home_care_guidance]
        return " ".join(texts) if texts else "Monitor your pet closely and contact a vet if things change or do not improve."
    if urgency == UrgencyLevel.vet_soon:
        return "Arrange a veterinary appointment within the next few days."
    if urgency == UrgencyLevel.vet_24h:
        return "Please arrange a veterinary appointment within 24 hours."
    return "This needs emergency veterinary attention now. Contact an emergency clinic immediately."
