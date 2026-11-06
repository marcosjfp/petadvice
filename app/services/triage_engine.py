import json
from collections.abc import Iterable
from datetime import date, timedelta
from functools import lru_cache

from sqlalchemy import update
from sqlmodel import Session

from app.content.loader import content_library
from app.i18n import DEFAULT_LANGUAGE, message
from app.models.schema import ConditionEntry, GuestContext, NeuterStatus, Pet, RelatedCare, ReportPet, RecordedAnswer, ResultReason, TriageAnswerRequest, TriageQuestion, TriageResult, TriageSession, UrgencyLevel, WatchSign
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


# Representative ages for the guest age groups. They sit well inside the
# puppy/kitten and senior ranges for every breed size, so calculate_life_stage
# gives the intended stage. A guest "adult" matches every adult stage.
_GUEST_AGE_YEARS = {'young': 0.25, 'adult': 4.0, 'senior': 13.0}
_ADULT_STAGES = frozenset({'young_adult', 'mature_adult'})


def apply_guest_context(pet: Pet, context: GuestContext | None) -> Pet:
    """Store optional guest details on the throwaway guest pet. "Not sure" stays None."""
    if context is None:
        return pet
    if context.age_group:
        pet.date_of_birth = date.today() - timedelta(days=round(_GUEST_AGE_YEARS[context.age_group] * 365.25))
    pet.sex = context.sex
    pet.neutered = context.neutered
    return pet


def guest_age_group(pet: Pet) -> str | None:
    """The age group a guest chose; None for saved pets and guests who were not sure."""
    if pet.owner_id is not None or pet.date_of_birth is None:
        return None
    stage = calculate_life_stage(pet)
    return 'young' if stage in ('puppy', 'kitten') else 'senior' if stage == 'senior' else 'adult'


def _scope_life_stages(pet: Pet) -> set[str] | None:
    life_stage = calculate_life_stage(pet)
    if life_stage is None:
        return None
    if guest_age_group(pet) == 'adult':
        return set(_ADULT_STAGES)
    return {life_stage}


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


def _missing_scope_details(pet: Pet, condition: ConditionEntry) -> list[str] | None:
    """None if the pet is known to be out of scope, else the unknown details the scope needs."""
    if condition.species not in (pet.species, condition.species.both):
        return None
    stages = _scope_life_stages(pet)
    if condition.applicable_life_stages and stages and not stages & set(condition.applicable_life_stages):
        return None
    missing = []
    if condition.applicable_sex:
        if pet.sex is None:
            missing.append('sex')
        elif pet.sex not in condition.applicable_sex:
            return None
    if condition.applicable_neuter_status:
        if pet.neutered is None:
            missing.append('neutered')
        elif (NeuterStatus.neutered if pet.neutered else NeuterStatus.intact) not in condition.applicable_neuter_status:
            return None
    return missing


def _pet_matches_condition_scope(pet: Pet, condition: ConditionEntry) -> bool:
    return _missing_scope_details(pet, condition) == []


def _life_stage_escalation(pet: Pet, condition: ConditionEntry) -> tuple[str, UrgencyLevel] | None:
    options = [(stage, condition.life_stage_escalation[stage]) for stage in sorted(_scope_life_stages(pet) or ()) if stage in condition.life_stage_escalation]
    return max(options, key=lambda item: item[1].rank, default=None)


@lru_cache(maxsize=1024)
def _longest_path(question_id: str, version: str | None) -> int:
    # The question graph is validated as acyclic when content loads.
    question = content_library.question_by_id(question_id)
    if question is None:
        return 0
    return 1 + max((_longest_path(next_id, version) for next_id in set(question.next_question_by_answer.values())), default=0)


def progress(session: TriageSession) -> dict | None:
    """Step number of the current question and the most questions the check can need."""
    if session.current_question_id is None:
        return None
    answered = len(json.loads(session.answers_json))
    return {'step': answered + 1, 'max_steps': answered + _longest_path(session.current_question_id, content_library.version)}


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


def go_back(db: Session, session_id: str, current_question_id: str) -> tuple[TriageSession, TriageQuestion]:
    """Return to the previously answered question and drop its answer.

    Only an unfinished check can be rewound, and only from the question the
    client is showing, so a stale tab cannot undo a newer answer.
    """
    session = db.get(TriageSession, session_id)
    if session is None:
        raise UnknownSessionError(session_id)
    answers = json.loads(session.answers_json)
    if session.result_snapshot is not None or session.current_question_id is None or session.current_question_id != current_question_id or not answers:
        raise InvalidAnswerError(current_question_id)
    previous_id = list(answers)[-1]  # JSON keeps the order the answers were given.
    previous = content_library.question_by_id(previous_id)
    if previous is None or previous.symptom_tag != session.symptom_entry_point:
        raise InvalidAnswerError(current_question_id)
    del answers[previous_id]
    changed = db.execute(
        update(TriageSession).where(
            TriageSession.id == session_id,
            TriageSession.current_question_id == current_question_id,
            TriageSession.answers_json == session.answers_json,
            TriageSession.result_snapshot.is_(None),
        ).values(answers_json=json.dumps(answers), current_question_id=previous_id)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise InvalidAnswerError(current_question_id)
    db.commit()
    db.refresh(session)
    return session, previous


def compute_result(db: Session, session_id: str, language: str = DEFAULT_LANGUAGE) -> TriageResult:
    """The first result is stored in the requesting language and kept as recorded."""
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
            answers=[RecordedAnswer(question_id=key, prompt=message(language, 'question_id', id=key), answer=value) for key, value in json.loads(session.answers_json).items()],
            started_at=as_utc(session.started_at), symptom=session.symptom_entry_point,
            recorded_at=utcnow(), historical=True, language=language,
        ))

    matched = content_library.conditions_for_symptom(session.symptom_entry_point)
    candidates = [condition for condition in matched if _pet_matches_condition_scope(pet, condition)]
    # Never substitute entries for another species or known incompatible scope.
    # A check without applicable content cannot justify home-care reassurance.
    urgency = max((condition.urgency_default for condition in candidates), key=lambda item: item.rank, default=UrgencyLevel.vet_24h)
    localized = {condition.id: content_library.localize_condition(condition, language) for condition in candidates}
    reasons = [ResultReason(kind='symptom_guidance', detail=message(language, 'reason.symptom_guidance', name=localized[condition.id].name), urgency=condition.urgency_default) for condition in candidates]
    if not candidates:
        reasons.append(ResultReason(kind='limited_content', detail=message(language, 'reason.limited_content'), urgency=urgency))
    if session.resulting_urgency and session.resulting_urgency.rank > urgency.rank:
        urgency = session.resulting_urgency
    life_stage = calculate_life_stage(pet)
    age_group = guest_age_group(pet)
    for condition in candidates:
        escalation = _life_stage_escalation(pet, condition)
        if escalation:
            stage, level = escalation
            reasons.append(ResultReason(kind='life_stage', detail=message(language, 'reason.life_stage', name=localized[condition.id].name, life_stage=message(language, f'life_stage.{stage}')), urgency=level))
            if level.rank > urgency.rank:
                urgency = level
    answers = json.loads(session.answers_json)

    for question in content_library.questions_for_symptom(session.symptom_entry_point):
        answer = answers.get(question.id)
        if answer in question.escalate_if:
            escalation = question.escalate_if[answer]
            reasons.append(ResultReason(kind='answer', detail=message(language, 'reason.answer', prompt=content_library.question_prompt(question, language), answer=content_library.option_label(question, answer, language)), urgency=escalation))
            if escalation.rank > urgency.rank:
                urgency = escalation

    # Red flags are not matched against answer text: substring matching made
    # "Yes" match "sunken eyes" and "Once" match "once or twice a month".
    # Answer-based escalation comes from the questions' escalate_if rules; the
    # red flags are returned as signs to watch for.
    watch_for: dict[str, WatchSign] = {}
    for condition in candidates:
        for flag in condition.red_flags:
            text = content_library.localize_flag(condition, flag, language)
            watch_for.setdefault(text, WatchSign(description=text, urgency=flag.escalates_to))

    guidance = _build_guidance(urgency, [localized[item.id] for item in candidates], language)
    result = TriageResult(
        session_id=session.id,
        resulting_urgency=urgency,
        resulting_guidance=guidance,
        matched_condition_ids=[item.id for item in candidates],
        possible_causes=_ordered_unique(cause for condition in localized.values() for cause in condition.possible_causes),
        recommended_examinations=_ordered_unique(exam for condition in localized.values() for exam in condition.recommended_examinations),
        reasons=[reason for reason in reasons if reason.urgency == urgency],
        answers=[_recorded_answer(key, value, language) for key, value in answers.items()],
        # A guest's birth date is only a stand-in for the age group they chose.
        pet=ReportPet(
            name=pet.name, species=pet.species, date_of_birth=None if age_group else pet.date_of_birth,
            life_stage=None if age_group == 'adult' else life_stage, age_group=age_group,
            sex=pet.sex, neutered=pet.neutered, breed_size=pet.breed_size,
        ),
        started_at=as_utc(session.started_at), recorded_at=utcnow(), symptom=session.symptom_entry_point,
        sources=sorted({source for condition in candidates for source in condition.sources}),
        related_care=_related_care(candidates, pet.species.value, language),
        content_version=content_library.version, language=language,
        # Most urgent signs first; the sort is stable, so authored order is kept within a level.
        watch_for=sorted(watch_for.values(), key=lambda item: -item.urgency.rank),
        recheck_advice=message(language, 'recheck.monitor_home') if urgency == UrgencyLevel.monitor_home else None,
        context_notes=_context_notes(pet, matched, life_stage, language),
    )
    return _save_snapshot(db, session, result)


def _ordered_unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _context_notes(pet: Pet, matched: list[ConditionEntry], life_stage: str | None, language: str) -> list[ResultReason]:
    """Name guidance that was not used only because a pet detail is unknown.

    The urgency is never lowered for unknown details; these notes tell the
    owner which detail would change the advice.
    """
    notes = []
    for condition in matched:
        missing = _missing_scope_details(pet, condition)
        if missing is None:
            continue
        name = content_library.localize_condition(condition, language).name
        if missing:
            scope = [message(language, f'scope.{sex.value}') for sex in condition.applicable_sex]
            scope += [message(language, f'scope.{status.value}') for status in condition.applicable_neuter_status]
            notes.append(ResultReason(kind='missing_context', urgency=condition.urgency_default, detail=message(
                language, 'reason.missing_context', name=name, scope=', '.join(scope),
                details=message(language, 'detail.join').join(message(language, f'detail.{item}') for item in missing),
                urgency=message(language, f'urgency.{condition.urgency_default.value}'),
            )))
        elif life_stage is None and condition.life_stage_escalation:
            by_level: dict[UrgencyLevel, list[str]] = {}
            other_species_stage = 'kitten' if pet.species.value == 'dog' else 'puppy'
            for stage, level in condition.life_stage_escalation.items():
                if level.rank > condition.urgency_default.rank and stage != other_species_stage:
                    by_level.setdefault(level, []).append(message(language, f'life_stage.{stage}'))
            for level, stages in sorted(by_level.items(), key=lambda item: -item[0].rank):
                notes.append(ResultReason(kind='missing_life_stage', urgency=level, detail=message(
                    language, 'reason.missing_life_stage', name=name, life_stages=message(language, 'list.or').join(stages),
                    urgency=message(language, f'urgency.{level.value}'),
                )))
    return notes


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


def _related_care(candidates: list[ConditionEntry], species: str, language: str) -> list[RelatedCare]:
    # Copied into the snapshot so a saved report shows the guides it was given.
    seen: dict[str, RelatedCare] = {}
    for condition in candidates:
        for item in content_library.related_care(condition, species, language):
            seen.setdefault(item.id, RelatedCare(id=item.id, title=item.title, description=item.description, recurrence=item.recurrence))
    return list(seen.values())


def _recorded_answer(question_id: str, answer: str, language: str) -> RecordedAnswer:
    question = content_library.question_by_id(question_id)
    if question is None:
        return RecordedAnswer(question_id=question_id, prompt=message(language, 'question_id', id=question_id), answer=answer)
    return RecordedAnswer(question_id=question_id, prompt=content_library.question_prompt(question, language), answer=content_library.option_label(question, answer, language))


def _build_guidance(urgency: UrgencyLevel, candidates: list[ConditionEntry], language: str) -> str:
    if urgency == UrgencyLevel.monitor_home:
        texts = [item.home_care_guidance for item in candidates if item.home_care_guidance]
        if texts:
            return " ".join(texts)
    return message(language, f'guidance.{urgency.value}')
