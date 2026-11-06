import json

import pytest
from fastapi.testclient import TestClient

from app.content.loader import TRANSLATIONS_DIR, ContentLibrary, content_library
from app.i18n import normalize_language
from app.main import app
from app.models.schema import Sex, Species, TriageAnswerRequest, UrgencyLevel
from app.services import triage_engine
from tests.test_backend import complete_remaining_questions, db, make_pet  # noqa: F401


@pytest.fixture(scope="module", autouse=True)
def load_content():
    content_library.load()


@pytest.mark.parametrize(("header", "expected"), [
    (None, "en"), ("", "en"), ("pt-PT,pt;q=0.9,en;q=0.8", "pt"), ("es-ES", "es"),
    ("fr-FR, es;q=0.5", "es"), ("pt-BR", "pt"), ("de", "en"),
])
def test_accept_language_negotiation(header, expected):
    assert normalize_language(header) == expected


@pytest.mark.parametrize("language", ["pt", "es"])
def test_translations_cover_all_published_content(language):
    data = json.loads((TRANSLATIONS_DIR / f"{language}.json").read_text())
    for condition in content_library.conditions:
        fields = data["conditions"][condition.id]
        assert fields["name"] and len(fields["red_flags"]) == len(condition.red_flags)
        for name in ("home_care_guidance", "prevention_tips"):
            assert (name in fields) == (getattr(condition, name) is not None), (condition.id, name)
        for name in ("possible_causes", "recommended_examinations"):
            assert len(fields.get(name, [])) == len(getattr(condition, name)), (condition.id, name)
    for item in content_library.preventive_items:
        fields = data["preventive_care"][item.id]
        assert fields["title"] and fields["description"] and ("recurrence" in fields) == (item.recurrence is not None)
        assert ("summary" in fields) == (item.summary is not None), item.id
        assert len(fields.get("steps", [])) == len(item.steps), item.id
    for question in content_library.questions:
        fields = data["questions"][question.id]
        assert fields["prompt"] and len(fields["options"]) == len(question.options)


def test_malformed_translation_is_rejected(monkeypatch, tmp_path):
    (tmp_path / "pt.json").write_text(json.dumps({"questions": {"q-vomit-001": {"options": ["Uma vez"]}}}))
    monkeypatch.setattr("app.content.loader.TRANSLATIONS_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="must have 3 items"):
        ContentLibrary().load()


def test_care_items_for_all_life_stages_are_included():
    puppy_items = {item.id for item in content_library.filter_preventive("dog", "puppy")}
    assert {"prevent-002", "prevent-005", "prevent-008", "prevent-009", "prevent-010"} <= puppy_items
    assert "prevent-007" not in puppy_items  # cat nail care
    senior_cat = {item.id for item in content_library.filter_preventive("cat", "senior")}
    assert {"prevent-006", "prevent-007"} <= senior_cat and "prevent-002" not in senior_cat


def test_api_returns_localized_content_with_canonical_answer_values():
    client = TestClient(app)
    conditions = client.get("/conditions", params={"species": "cat"}, headers={"Accept-Language": "pt-PT"}).json()
    assert any(item["name"] == "Stress ou ansiedade em gatos" for item in conditions)
    care = client.get("/preventive-care", params={"species": "dog"}, headers={"Accept-Language": "es"}).json()
    assert any(item["title"] == "Mantener las uñas con una longitud saludable" for item in care)
    english = client.get("/preventive-care", params={"species": "dog"}).json()
    assert any(item["title"] == "Keep nails at a healthy length" for item in english)
    question = content_library.present_question(content_library.question_by_id("q-vomit-001"), "es")
    assert question["options"] == ["Once", "2-3 times", "More than 3 times in a few hours"]
    assert question["option_labels"][0] == "Una vez" and question["prompt"].startswith("¿Cuántas")


def test_result_is_recorded_in_requested_language_with_same_urgency(db):
    results = {}
    for language in ("en", "pt"):
        pet = make_pet(db, species=Species.dog)
        session, _ = triage_engine.start_session(db, pet, "vomiting")
        triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-vomit-001", answer="More than 3 times in a few hours"))
        complete_remaining_questions(db, session.id)
        results[language] = triage_engine.compute_result(db, session.id, language)
    assert results["en"].resulting_urgency == results["pt"].resulting_urgency == UrgencyLevel.vet_24h
    assert results["pt"].language == "pt"
    assert results["pt"].resulting_guidance.startswith("Marque uma consulta")
    assert results["pt"].answers[0].answer == "Mais de 3 vezes em poucas horas"
    assert any("A sua resposta" in reason.detail for reason in results["pt"].reasons)
    # The stored report keeps its original language when viewed later in another one.
    assert triage_engine.compute_result(db, results["pt"].session_id, "en").resulting_guidance == results["pt"].resulting_guidance


@pytest.mark.parametrize(("answers", "expected"), [
    ({}, UrgencyLevel.vet_soon),
    ({"q-scooting-001": "Yes"}, UrgencyLevel.vet_24h),
    ({"q-scooting-003": "Yes"}, UrgencyLevel.vet_24h),
])
def test_scooting_check(db, answers, expected):
    pet = make_pet(db, species=Species.dog)
    session, first = triage_engine.start_session(db, pet, "scooting")
    question = first
    while question is not None:
        _, question, _ = triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id=question.id, answer=answers.get(question.id, "No")))
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == expected
    assert "dog-cat-parasite-002" in result.matched_condition_ids


@pytest.mark.parametrize(("first_answer", "expected"), [
    ("No", UrgencyLevel.monitor_home),
    ("Peeing outside the box or blood in the urine", UrgencyLevel.vet_24h),
    ("Straining with little or no urine", UrgencyLevel.emergency_now),
])
def test_stressed_cat_check(db, first_answer, expected):
    pet = make_pet(db, species=Species.cat, sex=Sex.female)
    session, _ = triage_engine.start_session(db, pet, "nervous_or_stressed")
    triage_engine.answer_question(db, session.id, TriageAnswerRequest(question_id="q-stress-001", answer=first_answer))
    complete_remaining_questions(db, session.id)
    result = triage_engine.compute_result(db, session.id)
    assert result.resulting_urgency == expected
    if expected == UrgencyLevel.monitor_home:
        assert "pheromones" in result.resulting_guidance


def test_new_content_has_follow_ups():
    for condition_id in ("dog-cat-parasite-001", "dog-cat-parasite-002", "cat-behav-001"):
        assert content_library.condition_by_id(condition_id).related_care
    for item_id in ("prevent-005", "prevent-006", "prevent-009", "prevent-010"):
        assert content_library.preventive_by_id(item_id).related_symptoms
    flea = content_library.condition_by_id("dog-cat-parasite-001").home_care_guidance
    assert "Care section" not in flea


def test_broken_follow_up_link_is_rejected():
    library = ContentLibrary()
    library.load()
    library.conditions[0].related_care.append("prevent-missing")
    with pytest.raises(ValueError, match="unknown care items"):
        ContentLibrary._validate_links(library.conditions, library.preventive_items, library.questions)
    library.preventive_items[0].related_symptoms.append("not-a-check")
    library.conditions[0].related_care.pop()
    with pytest.raises(ValueError, match="without a check"):
        ContentLibrary._validate_links(library.conditions, library.preventive_items, library.questions)


def test_result_and_learn_include_related_care_for_the_pet_species(db):
    pet = make_pet(db, species=Species.dog)
    session, _ = triage_engine.start_session(db, pet, "scratching")
    complete_remaining_questions(db, session.id)
    result = triage_engine.compute_result(db, session.id, "pt")
    assert [item.id for item in result.related_care] == ["prevent-005", "prevent-010"]
    assert result.related_care[0].title == "Tratar uma infestação de pulgas em casa"
    client = TestClient(app)
    wound = next(item for item in client.get("/conditions", params={"species": "dog"}).json() if item["id"] == "dog-cat-wound-001")
    assert [item["id"] for item in wound["related_care_items"]] == ["prevent-008"]  # the cat nail guide is filtered out


def test_care_guides_have_topics_steps_and_reminder_intervals():
    items = {item.id: item for item in content_library.preventive_items}
    assert all(item.topic for item in items.values())
    assert {item.topic.value for item in items.values()} >= {"vaccinations", "parasites", "dental", "nutrition", "health_checks", "grooming", "behaviour", "reproduction", "getting_started"}
    for item_id in ("prevent-001", "prevent-005", "prevent-006", "prevent-007", "prevent-008", "prevent-009", "prevent-010"):
        assert items[item_id].summary and len(items[item_id].steps) >= 3, item_id
    for item in items.values():
        if item.steps:  # the plain-text description must stay a complete fallback, not just the summary
            assert len(item.description) > len(item.summary), item.id
        if item.reminder_interval_days:
            assert item.recurrence, item.id
    assert items["prevent-013"].reminder_interval_days == 1
    assert items["prevent-015"].reminder_interval_days == 182
    assert items["prevent-016"].reminder_interval_days is None  # one-off reminder


@pytest.mark.parametrize(("species", "stage", "expected", "excluded"), [
    ("dog", "puppy", {"prevent-011", "prevent-013", "prevent-014", "prevent-016"}, {"prevent-012", "prevent-015", "prevent-017"}),
    ("cat", "kitten", {"prevent-012", "prevent-013", "prevent-014", "prevent-017"}, {"prevent-011", "prevent-015", "prevent-016"}),
    ("cat", "senior", {"prevent-012", "prevent-013", "prevent-014", "prevent-015"}, {"prevent-017"}),
])
def test_essential_care_content_is_species_and_stage_appropriate(species, stage, expected, excluded):
    ids = {item.id for item in content_library.filter_preventive(species, stage)}
    assert expected <= ids and not (excluded & ids)


def test_care_api_returns_localized_steps_and_grouping_fields():
    client = TestClient(app)
    care = client.get("/preventive-care", params={"species": "cat", "life_stage": "senior"}, headers={"Accept-Language": "pt-PT"}).json()
    dental = next(item for item in care if item["id"] == "prevent-013")
    assert dental["topic"] == "dental" and dental["reminder_interval_days"] == 1
    assert dental["title"].startswith("Escovar") and dental["summary"] and dental["steps"][0].startswith("Use uma escova")
    english = next(item for item in client.get("/preventive-care", params={"species": "cat"}).json() if item["id"] == "prevent-013")
    assert len(english["steps"]) == len(dental["steps"]) and "xylitol" in english["steps"][0]
    assert "xylitol" in english["description"]  # description stays a complete fallback


@pytest.mark.parametrize(("fields", "message"), [
    ({"steps": ["Só um passo"]}, "must have 4 items"),
    ({"topic": "dental"}, "invalid fields"),
    ({"reminder_interval_days": "7"}, "invalid fields"),
])
def test_malformed_care_translation_is_rejected(monkeypatch, tmp_path, fields, message):
    (tmp_path / "pt.json").write_text(json.dumps({"preventive_care": {"prevent-001": fields}}))
    monkeypatch.setattr("app.content.loader.TRANSLATIONS_DIR", tmp_path)
    with pytest.raises(RuntimeError, match=message):
        ContentLibrary().load()


def test_care_translation_cannot_add_a_summary_missing_in_english(monkeypatch, tmp_path):
    (tmp_path / "pt.json").write_text(json.dumps({"preventive_care": {"prevent-002": {"summary": "Resumo"}}}))
    monkeypatch.setattr("app.content.loader.TRANSLATIONS_DIR", tmp_path)
    with pytest.raises(RuntimeError, match="invalid fields"):
        ContentLibrary().load()


@pytest.mark.parametrize(("update", "message"), [
    ({"steps": ["Do this"], "summary": None}, "steps but no summary"),
    ({"steps": ["  "], "summary": "Short"}, "empty step"),
    ({"reminder_interval_days": 7, "recurrence": None}, "no recurrence"),
    ({"reminder_interval_days": 0, "recurrence": "daily"}, "greater than or equal to 1"),
    ({"topic": "astrology"}, "topic"),
])
def test_care_item_shape_is_validated(update, message):
    from pydantic import ValidationError
    from app.models.schema import PreventiveCareItem
    base = {"id": "x", "species": "dog", "life_stage": "all", "topic": "dental", "title": "T", "description": "D"}
    with pytest.raises(ValidationError, match=message):
        PreventiveCareItem.model_validate(base | update)
