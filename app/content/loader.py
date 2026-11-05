import json
import hashlib
from pathlib import Path

from pydantic import ValidationError

from app.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES
from app.models.schema import ConditionEntry, PreventiveCareItem, RedFlag, TriageQuestion, UrgencyLevel

CONTENT_DIR = Path(__file__).parent
QUESTIONS_FILE = CONTENT_DIR / "triage_questions.json"
TRANSLATIONS_DIR = CONTENT_DIR / "translations"
ALL_LIFE_STAGES = "all"
_CONDITION_TEXT = ("name", "home_care_guidance", "prevention_tips")
_CONDITION_LISTS = ("possible_causes", "recommended_examinations")
_PREVENTIVE_TEXT = ("title", "description", "recurrence")


class ContentLibrary:
    def __init__(self) -> None:
        self.conditions: list[ConditionEntry] = []
        self.preventive_items: list[PreventiveCareItem] = []
        self.questions: list[TriageQuestion] = []
        self.version: str | None = None
        self.translations: dict[str, dict] = {}

    def load(self) -> None:
        self.conditions, self.preventive_items = [], []
        batch_files = sorted(CONTENT_DIR.glob("*content-batch*.json"))
        if not batch_files:
            raise RuntimeError(f"No content batch files found in {CONTENT_DIR}")
        try:
            conditions: list[ConditionEntry] = []
            preventive_items: list[PreventiveCareItem] = []
            for batch_file in batch_files:
                data = json.loads(batch_file.read_text())
                conditions += [ConditionEntry.model_validate(item) for item in data.get("condition_entries", [])]
                preventive_items += [PreventiveCareItem.model_validate(item) for item in data.get("preventive_care_items", [])]

            seen: set[str] = set()
            for condition in conditions:
                if condition.id in seen:
                    raise ValueError(f"Duplicate ConditionEntry id across batches: {condition.id}")
                seen.add(condition.id)

            questions = []
            if QUESTIONS_FILE.exists():
                questions = [TriageQuestion.model_validate(item) for item in json.loads(QUESTIONS_FILE.read_text())]
            self._validate_questions(questions)
            self._validate_links(conditions, preventive_items, questions)
            if len({item.id for item in preventive_items}) != len(preventive_items):
                raise ValueError("Duplicate preventive care id across batches")
            invalid_home_care = [item.id for item in conditions if item.urgency_default != UrgencyLevel.monitor_home and item.home_care_guidance]
            if invalid_home_care:
                raise ValueError(f"home_care_guidance is only allowed for monitor_home entries: {invalid_home_care}")
            translation_files = sorted(TRANSLATIONS_DIR.glob("*.json"))
            translations = {path.stem: json.loads(path.read_text()) for path in translation_files}
            self._validate_translations(translations, conditions, preventive_items, questions)
        except (OSError, KeyError, json.JSONDecodeError, ValidationError, ValueError) as error:
            raise RuntimeError(f"Content library failed schema validation: {error}") from error
        self.conditions = conditions
        self.preventive_items = preventive_items
        self.questions = questions
        self.translations = translations
        digest = hashlib.sha256()
        for path in [*batch_files, QUESTIONS_FILE, *translation_files]:
            if path.exists():
                digest.update(path.name.encode())
                digest.update(path.read_bytes())
        self.version = digest.hexdigest()

    @staticmethod
    def _validate_questions(questions: list[TriageQuestion]) -> None:
        by_id = {question.id: question for question in questions}
        if len(by_id) != len(questions):
            raise ValueError("Duplicate triage question id")
        for question in questions:
            options = set(question.options)
            if not options or len(options) != len(question.options):
                raise ValueError(f"Question needs unique options: {question.id}")
            if not (set(question.escalate_if) | set(question.next_question_by_answer)) <= options:
                raise ValueError(f"Question references an invalid answer: {question.id}")
            for next_id in question.next_question_by_answer.values():
                target = by_id.get(next_id)
                if target is None or target.symptom_tag != question.symptom_tag:
                    raise ValueError(f"Invalid question branch: {question.id} -> {next_id}")
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(question_id: str) -> None:
            if question_id in visiting:
                raise ValueError(f"Cycle in triage questions: {question_id}")
            if question_id in visited:
                return
            visiting.add(question_id)
            for next_id in by_id[question_id].next_question_by_answer.values():
                visit(next_id)
            visiting.remove(question_id)
            visited.add(question_id)

        for question in questions:
            visit(question.id)
        for symptom in {question.symptom_tag for question in questions}:
            group = [question for question in questions if question.symptom_tag == symptom]
            if sum(question.is_entry_point for question in group) != 1:
                raise ValueError(f"Symptom needs exactly one entry question: {symptom}")

    @staticmethod
    def _validate_links(conditions: list[ConditionEntry], preventive_items: list[PreventiveCareItem], questions: list[TriageQuestion]) -> None:
        care_ids = {item.id for item in preventive_items}
        checkable = {question.symptom_tag for question in questions} | {tag for condition in conditions for tag in condition.symptom_tags}
        for condition in conditions:
            missing = set(condition.related_care) - care_ids
            if missing:
                raise ValueError(f"{condition.id} links to unknown care items: {sorted(missing)}")
        for item in preventive_items:
            missing = set(item.related_symptoms) - checkable
            if missing:
                raise ValueError(f"{item.id} links to symptoms without a check: {sorted(missing)}")

    def related_care(self, condition: ConditionEntry, species: str | None, language: str) -> list[PreventiveCareItem]:
        items = [self.preventive_by_id(item_id) for item_id in condition.related_care]
        return [self.localize_preventive(item, language) for item in items if item and (species is None or item.species.value in (species, "both"))]

    def preventive_by_id(self, item_id: str) -> PreventiveCareItem | None:
        return next((item for item in self.preventive_items if item.id == item_id), None)

    @staticmethod
    def _validate_translations(translations: dict[str, dict], conditions: list[ConditionEntry], preventive_items: list[PreventiveCareItem], questions: list[TriageQuestion]) -> None:
        """Translations may be incomplete (English is the fallback) but must match the source shape."""
        by_kind = {
            "conditions": {item.id: item for item in conditions},
            "preventive_care": {item.id: item for item in preventive_items},
            "questions": {item.id: item for item in questions},
        }
        for language, data in translations.items():
            if language not in SUPPORTED_LANGUAGES or language == DEFAULT_LANGUAGE:
                raise ValueError(f"Unsupported translation language: {language}")
            unknown_sections = set(data) - set(by_kind)
            if unknown_sections:
                raise ValueError(f"Unknown translation sections in {language}: {sorted(unknown_sections)}")
            for kind, entries in data.items():
                for item_id, fields in entries.items():
                    source = by_kind[kind].get(item_id)
                    if source is None:
                        raise ValueError(f"Translation {language} references unknown {kind} id: {item_id}")
                    list_fields = {"red_flags": [flag.description for flag in source.red_flags]} if kind == "conditions" else {}
                    if kind == "conditions":
                        list_fields |= {name: getattr(source, name) for name in _CONDITION_LISTS}
                    if kind == "questions":
                        list_fields["options"] = source.options
                    for name, value in fields.items():
                        if name in list_fields:
                            if not isinstance(value, list) or len(value) != len(list_fields[name]):
                                raise ValueError(f"Translation {language} {item_id}.{name} must have {len(list_fields[name])} items")
                        elif not hasattr(source, name) or not isinstance(value, str):
                            raise ValueError(f"Translation {language} {item_id} has an invalid field: {name}")

    def _translation(self, language: str, kind: str, item_id: str) -> dict:
        return self.translations.get(language, {}).get(kind, {}).get(item_id, {})

    def localize_condition(self, condition: ConditionEntry, language: str) -> ConditionEntry:
        fields = self._translation(language, "conditions", condition.id)
        if not fields:
            return condition
        update = {name: fields[name] for name in (*_CONDITION_TEXT, *_CONDITION_LISTS) if name in fields and getattr(condition, name) is not None}
        if "red_flags" in fields:
            update["red_flags"] = [RedFlag(description=text, escalates_to=flag.escalates_to) for flag, text in zip(condition.red_flags, fields["red_flags"])]
        return condition.model_copy(update=update)

    def localize_flag(self, condition: ConditionEntry, flag: RedFlag, language: str) -> str:
        texts = self._translation(language, "conditions", condition.id).get("red_flags")
        return texts[condition.red_flags.index(flag)] if texts else flag.description

    def localize_preventive(self, item: PreventiveCareItem, language: str) -> PreventiveCareItem:
        fields = self._translation(language, "preventive_care", item.id)
        update = {name: fields[name] for name in _PREVENTIVE_TEXT if name in fields and getattr(item, name) is not None}
        return item.model_copy(update=update) if update else item

    def question_prompt(self, question: TriageQuestion, language: str) -> str:
        return self._translation(language, "questions", question.id).get("prompt", question.prompt)

    def option_label(self, question: TriageQuestion, answer: str, language: str) -> str:
        labels = self._translation(language, "questions", question.id).get("options")
        return labels[question.options.index(answer)] if labels and answer in question.options else answer

    def present_question(self, question: TriageQuestion | None, language: str) -> dict | None:
        """Answers are submitted as the canonical option; option_labels are for display only."""
        if question is None:
            return None
        return question.model_dump() | {
            "prompt": self.question_prompt(question, language),
            "option_labels": [self.option_label(question, option, language) for option in question.options],
        }

    def conditions_for_symptom(self, symptom_tag: str) -> list[ConditionEntry]:
        return [condition for condition in self.conditions if symptom_tag in condition.symptom_tags]

    def condition_by_id(self, condition_id: str) -> ConditionEntry | None:
        return next((condition for condition in self.conditions if condition.id == condition_id), None)

    def question_by_id(self, question_id: str) -> TriageQuestion | None:
        return next((question for question in self.questions if question.id == question_id), None)

    def questions_for_symptom(self, symptom_tag: str) -> list[TriageQuestion]:
        return [question for question in self.questions if question.symptom_tag == symptom_tag]

    def filter_conditions(self, species=None, category=None, life_stage=None, symptom_tag=None, language=DEFAULT_LANGUAGE):
        results = self.conditions
        if species:
            results = [item for item in results if item.species.value in (species, "both")]
        if category:
            results = [item for item in results if item.category.value == category]
        if life_stage:
            results = [item for item in results if life_stage in item.applicable_life_stages]
        if symptom_tag:
            results = [item for item in results if symptom_tag in item.symptom_tags]
        return [self.localize_condition(item, language) for item in results]

    def filter_preventive(self, species=None, life_stage=None, language=DEFAULT_LANGUAGE):
        results = self.preventive_items
        if species:
            results = [item for item in results if item.species.value in (species, "both")]
        if life_stage:
            results = [item for item in results if item.life_stage in (life_stage, ALL_LIFE_STAGES)]
        return [self.localize_preventive(item, language) for item in results]


content_library = ContentLibrary()
