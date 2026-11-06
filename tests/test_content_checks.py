import json
import re
from pathlib import Path

import pytest

from app.content.loader import TRANSLATIONS_DIR, content_library
from app.models.schema import Species, TriageAnswerRequest, TriageSession, UrgencyLevel
from app.services import triage_engine
from tests.test_backend import complete_remaining_questions, db, make_pet  # noqa: F401

SYMPTOMS_TS = Path(__file__).resolve().parent.parent / "web" / "src" / "symptoms.ts"
I18N_TS = SYMPTOMS_TS.parent / "i18n.ts"

NEW_CHECKS = {
    "ate_something_toxic": ("dog", "cat"),
    "not_eating_or_lethargic": ("dog", "cat"),
    "coughing": ("dog", "cat"),
    "eye_problem": ("dog", "cat"),
    "ear_scratching_or_head_shaking": ("dog", "cat"),
    "constipation": ("dog", "cat"),
    "heatstroke": ("dog", "cat"),
    "swollen_belly_retching": ("dog",),
}


@pytest.fixture(scope="module", autouse=True)
def load_content():
    content_library.load()


def offered_symptoms() -> dict[str, str | None]:
    """Parse `{ value: 'tag', group: '…', only: 'dog' }` entries (fields in any order) from the frontend symptom list."""
    objects = re.findall(r"\{[^{}]*\bvalue:\s*'[^']+'[^{}]*\}", SYMPTOMS_TS.read_text())
    assert objects, "could not parse web/src/symptoms.ts"
    entries = {}
    for text in objects:
        only = re.search(r"\bonly:\s*'(dog|cat)'", text)
        entries[re.search(r"\bvalue:\s*'([^']+)'", text).group(1)] = only.group(1) if only else None
    return entries


def guest_pet(db, species):
    """Guests may only give a species: no age, sex or neuter status."""
    return make_pet(db, owner_id=None, species=species, sex=None, neutered=None, date_of_birth=None)


def run_check(db, pet, symptom, answers=None):
    session, _ = triage_engine.start_session(db, pet, symptom)
    for question_id, answer in (answers or {}).items():
        assert db.get(TriageSession, session.id).current_question_id == question_id
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id=question_id, answer=answer))
    complete_remaining_questions(db, session.id)
    return triage_engine.compute_result(db, session.id)


def test_every_offered_symptom_has_a_check_and_a_label():
    offered = offered_symptoms()
    assert set(NEW_CHECKS) <= set(offered)
    assert offered["swollen_belly_retching"] == "dog"
    i18n = I18N_TS.read_text()
    for tag, only in offered.items():
        # A check may be question-led or condition-only (start_session accepts either),
        # but every button must lead to condition guidance rather than the bare fallback.
        assert content_library.conditions_for_symptom(tag), tag
        questions = content_library.questions_for_symptom(tag)
        assert not questions or sum(question.is_entry_point for question in questions) == 1, tag
        assert len(re.findall(rf"\b{tag}: '", i18n)) == 3, f"{tag} needs an en, pt and es label"


@pytest.mark.parametrize("symptom", sorted(NEW_CHECKS))
def test_new_checks_have_entry_questions_and_species_content(symptom):
    questions = content_library.questions_for_symptom(symptom)
    assert 2 <= len(questions) <= 4
    assert sum(question.is_entry_point for question in questions) == 1
    for species in NEW_CHECKS[symptom]:
        conditions = [item for item in content_library.conditions_for_symptom(symptom) if item.species.value in (species, "both")]
        # Guests give only a species, so at least one entry must not depend on age, sex or neuter status.
        unscoped = [item for item in conditions if not item.applicable_sex and not item.applicable_neuter_status]
        assert unscoped, (symptom, species)
        for condition in unscoped:
            assert condition.red_flags and condition.possible_causes and condition.recommended_examinations and condition.prevention_tips
            assert 1 <= len(condition.sources) <= 3
            assert all(source.startswith("https://") for source in condition.sources)


@pytest.mark.parametrize("language", ["pt", "es"])
def test_new_checks_are_translated(language):
    data = json.loads((TRANSLATIONS_DIR / f"{language}.json").read_text())
    for symptom in NEW_CHECKS:
        for question in content_library.questions_for_symptom(symptom):
            fields = data["questions"][question.id]
            assert fields["prompt"] and len(fields["options"]) == len(question.options)
        for condition in content_library.conditions_for_symptom(symptom):
            fields = data["conditions"][condition.id]
            assert fields["name"] and len(fields["red_flags"]) == len(condition.red_flags)
            assert len(fields.get("possible_causes", [])) == len(condition.possible_causes)


def test_no_placeholder_sources():
    for condition in content_library.conditions:
        assert condition.sources, condition.id
        assert all(source.startswith("https://") for source in condition.sources), condition.id


@pytest.mark.parametrize("symptom", sorted(NEW_CHECKS))
def test_answer_text_cannot_raise_urgency_beyond_question_rules(symptom):
    """Red flags are also matched by answer text; keep that consistent with escalate_if.

    An answer may only appear inside a red flag when the question rule already
    escalates that answer at least as far, so the result is the same whether or
    not text matching is used.
    """
    conditions = content_library.conditions_for_symptom(symptom)
    for question in content_library.questions_for_symptom(symptom):
        for option in question.options:
            if len(option.strip()) <= 2:
                continue
            for condition in conditions:
                for flag in condition.red_flags:
                    if option.lower() in flag.description.lower():
                        rule = question.escalate_if.get(option)
                        assert rule and rule.rank >= flag.escalates_to.rank, (question.id, option, flag.description)


@pytest.mark.parametrize("species", [Species.dog, Species.cat])
def test_toxic_check_is_an_emergency_on_every_path(db, species):
    pet = guest_pet(db, species)
    result = run_check(db, pet, "ate_something_toxic")
    assert result.resulting_urgency == UrgencyLevel.emergency_now
    entry = next(question for question in content_library.questions_for_symptom("ate_something_toxic") if question.is_entry_point)
    assert "vomit" in entry.prompt and "packaging" in entry.prompt
    for option in entry.options:
        assert entry.escalate_if[option] == UrgencyLevel.emergency_now
        result = run_check(db, guest_pet(db, species), "ate_something_toxic", {entry.id: option})
        assert result.resulting_urgency == UrgencyLevel.emergency_now


def test_cat_toxic_check_includes_lily_and_permethrin_guidance(db):
    result = run_check(db, guest_pet(db, Species.cat), "ate_something_toxic")
    assert "cat-tox-002" in result.matched_condition_ids
    dog_result = run_check(db, guest_pet(db, Species.dog), "ate_something_toxic")
    assert "cat-tox-002" not in dog_result.matched_condition_ids


@pytest.mark.parametrize("answer", ["No", "Yes"])
def test_bloat_is_always_an_emergency(db, answer):
    for pet in (guest_pet(db, Species.dog), make_pet(db, species=Species.dog), guest_pet(db, Species.cat)):
        result = run_check(db, pet, "swollen_belly_retching", {"q-bloat-001": answer})
        assert result.resulting_urgency == UrgencyLevel.emergency_now


@pytest.mark.parametrize("species", [Species.dog, Species.cat])
def test_heatstroke_is_always_an_emergency(db, species):
    assert run_check(db, guest_pet(db, species), "heatstroke").resulting_urgency == UrgencyLevel.emergency_now


@pytest.mark.parametrize("species", [Species.dog, Species.cat])
def test_mild_paths_still_recommend_a_vet(db, species):
    for symptom in ("not_eating_or_lethargic", "coughing", "eye_problem", "ear_scratching_or_head_shaking", "constipation"):
        result = run_check(db, guest_pet(db, species), symptom)
        assert result.resulting_urgency.rank >= UrgencyLevel.vet_soon.rank, symptom
        assert result.matched_condition_ids, symptom


def test_cat_not_eating_for_a_day_is_urgent(db):
    result = run_check(db, guest_pet(db, Species.cat), "not_eating_or_lethargic", {"q-appetite-001": "No", "q-appetite-002": "24 to 48 hours"})
    assert result.resulting_urgency == UrgencyLevel.vet_24h


def test_constipation_with_little_urine_is_an_emergency(db):
    result = run_check(db, guest_pet(db, Species.cat), "constipation", {"q-constipation-001": "Little or no urine, or unsure"})
    assert result.resulting_urgency == UrgencyLevel.emergency_now


@pytest.mark.parametrize(("symptom", "answers"), [
    ("coughing", {"q-cough-001": "Yes"}),
    ("eye_problem", {"q-eye-001": "Suddenly cloudy or blue"}),
    ("not_eating_or_lethargic", {"q-appetite-001": "Yes"}),
])
def test_danger_answers_escalate_to_emergency(db, symptom, answers):
    assert run_check(db, guest_pet(db, Species.cat), symptom, answers).resulting_urgency == UrgencyLevel.emergency_now


def test_ear_balance_problems_escalate(db):
    result = run_check(db, guest_pet(db, Species.dog), "ear_scratching_or_head_shaking", {"q-ear-001": "Yes"})
    assert result.resulting_urgency == UrgencyLevel.vet_24h
