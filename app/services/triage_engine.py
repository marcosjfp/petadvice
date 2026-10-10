import json

from sqlalchemy import update
from sqlmodel import Session

from app.content.loader import content_library
from app.models.schema import ConditionEntry, NeuterStatus, Pet, RedFlag, ReportPet, RecordedAnswer, ResultReason, TriageAnswerRequest, TriageQuestion, TriageResult, TriageSession, UrgencyLevel
from app.services.life_stage_calculator import calculate_life_stage
from app.services.auth import as_utc, utcnow


class UnknownSessionError(Exception):
    pass


class InvalidAnswerError(Exception):
    pass


class UnsupportedSymptomError(Exception):
    pass


class IncompleteSessionError(Exception):
    pass


def _entry_question(symptom_tag: str) -> TriageQuestion | None:
    questions = content_library.questions_for_symptom(symptom_tag)
    return next((question for question in questions if question.is_entry_point), questions[0] if questions else None)


def start_session(db: Session, pet: Pet, symptom_tag: str) -> tuple[TriageSession, TriageQuestion | None]:
    if not content_library.conditions_for_symptom(symptom_tag) and not content_library.questions_for_symptom(symptom_tag):
        raise UnsupportedSymptomError(symptom_tag)
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
    if session.current_question_id != req.question_id or question.symptom_tag != session.symptom_entry_point:
        raise InvalidAnswerError(req.question_id)
    answers = json.loads(session.answers_json)
    answers[req.question_id] = req.answer
    next_id = question.next_question_by_answer.get(req.answer)
    next_question = content_library.question_by_id(next_id) if next_id else None
    # Compare-and-set prevents two requests that read the same question from
    # overwriting each other, including an emergency answer in another worker.
    changed = db.execute(
        update(TriageSession).where(
            TriageSession.id == session_id,
            TriageSession.current_question_id == req.question_id,
        ).values(
            answers_json=json.dumps(answers),
            current_question_id=next_question.id if next_question else None,
        )
    )
    if changed.rowcount != 1:
        db.rollback()
        raise InvalidAnswerError(req.question_id)
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
    if session.current_question_id is not None:
        raise IncompleteSessionError(session_id)
    if session.result_snapshot:
        return TriageResult.model_validate(session.result_snapshot)

    # Earlier releases stored only urgency/guidance. Preserve those historical
    # decisions; do not regenerate them using today's content or pet context.
    if session.resulting_urgency is not None and session.resulting_guidance:
        return _save_snapshot(db, session, TriageResult(
            session_id=session.id, resulting_urgency=session.resulting_urgency,
            resulting_guidance=session.resulting_guidance,
            matched_condition_ids=[item for item in session.condition_entries_matched_raw.split(',') if item],
            answers=[RecordedAnswer(question_id=key, prompt=f'Question ID: {key}', answer=value) for key, value in json.loads(session.answers_json).items()],
            started_at=as_utc(session.started_at), symptom=session.symptom_entry_point,
            recorded_at=utcnow(), historical=True,
        ))

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    candidates = [condition for condition in matched if _pet_matches_condition_scope(pet, condition)]
    # Never substitute entries for another species or known incompatible scope.
    # A check without applicable content cannot justify home-care reassurance.
    urgency = max((condition.urgency_default for condition in candidates), key=lambda item: item.rank, default=UrgencyLevel.vet_24h)
    reasons = [ResultReason(kind='symptom_guidance', detail=f'The existing symptom guidance for {condition.name} sets this minimum action level. This is not a diagnosis of that condition.', urgency=condition.urgency_default) for condition in candidates]
    if not candidates:
        reasons.append(ResultReason(kind='limited_content', detail='No condition guidance matches the available pet context. The check uses the existing cautious fallback.', urgency=urgency))
    if session.resulting_urgency and session.resulting_urgency.rank > urgency.rank:
        urgency = session.resulting_urgency
    life_stage = calculate_life_stage(pet)
    for condition in candidates:
        escalation = condition.life_stage_escalation.get(life_stage) if life_stage else None
        if escalation:
            reasons.append(ResultReason(kind='life_stage', detail=f'The existing guidance for {condition.name} includes a higher action level for the {life_stage.replace("_", " ")} life stage.', urgency=escalation))
        if escalation and escalation.rank > urgency.rank:
            urgency = escalation
    answers = json.loads(session.answers_json)

    for question in content_library.questions_for_symptom(session.symptom_entry_point):
        answer = answers.get(question.id)
        if answer in question.escalate_if:
            escalation = question.escalate_if[answer]
            reasons.append(ResultReason(kind='answer', detail=f'{question.prompt} Your answer: {answer}. The existing question rule sets this action level.', urgency=escalation))
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
                reasons.append(ResultReason(kind='red_flag', detail=f'An answer matched this existing warning rule: {flag.description}', urgency=flag.escalates_to))
                if flag.escalates_to.rank > urgency.rank:
                    urgency = flag.escalates_to

    guidance = _build_guidance(urgency, candidates)
    result = TriageResult(
        session_id=session.id,
        resulting_urgency=urgency,
        resulting_guidance=guidance,
        matched_condition_ids=[item.id for item in candidates],
        possible_causes=sorted({cause for condition in candidates for cause in condition.possible_causes}),
        recommended_examinations=sorted({exam for condition in candidates for exam in condition.recommended_examinations}),
        reasons=[reason for reason in reasons if reason.urgency == urgency],
        answers=[RecordedAnswer(question_id=key, prompt=content_library.question_by_id(key).prompt if content_library.question_by_id(key) else f'Question ID: {key}', answer=value) for key, value in answers.items()],
        pet=ReportPet(name=pet.name, species=pet.species, date_of_birth=pet.date_of_birth, life_stage=life_stage, sex=pet.sex, neutered=pet.neutered, breed_size=pet.breed_size),
        started_at=as_utc(session.started_at), recorded_at=utcnow(), symptom=session.symptom_entry_point,
        sources=sorted({source for condition in candidates for source in condition.sources}),
        content_version=content_library.version,
    )
    return _save_snapshot(db, session, result)


def _save_snapshot(db: Session, session: TriageSession, result: TriageResult) -> TriageResult:
    # Only the first result is stored, even if simultaneous requests finish the
    # same check. JSON stores copies of content and context, not live references.
    db.execute(update(TriageSession).where(TriageSession.id == session.id, TriageSession.result_snapshot.is_(None)).values(
        result_snapshot=result.model_dump(mode='json'), resulting_urgency=result.resulting_urgency,
        resulting_guidance=result.resulting_guidance, condition_entries_matched_raw=','.join(result.matched_condition_ids),
    ))
    db.commit()
    db.refresh(session)
    return TriageResult.model_validate(session.result_snapshot)


def _build_guidance(urgency: UrgencyLevel, candidates: list[ConditionEntry]) -> str:
    if urgency == UrgencyLevel.monitor_home:
        texts = [item.home_care_guidance for item in candidates if item.home_care_guidance]
        return " ".join(texts) if texts else "Monitor your pet closely and contact a vet if things change or do not improve."
    if urgency == UrgencyLevel.vet_soon:
        return "Arrange a veterinary appointment within the next few days."
    if urgency == UrgencyLevel.vet_24h:
        return "Please arrange a veterinary appointment within 24 hours."
    return "This needs emergency veterinary attention now. Contact an emergency clinic immediately."
