import json
from pathlib import Path

from pydantic import ValidationError

from app.models.schema import ConditionEntry, PreventiveCareItem, TriageQuestion, UrgencyLevel

CONTENT_DIR = Path(__file__).parent
QUESTIONS_FILE = CONTENT_DIR / "triage_questions.json"


class ContentLibrary:
    def __init__(self) -> None:
        self.conditions: list[ConditionEntry] = []
        self.preventive_items: list[PreventiveCareItem] = []
        self.questions: list[TriageQuestion] = []

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
            invalid_home_care = [item.id for item in conditions if item.urgency_default != UrgencyLevel.monitor_home and item.home_care_guidance]
            if invalid_home_care:
                raise ValueError(f"home_care_guidance is only allowed for monitor_home entries: {invalid_home_care}")
        except (OSError, KeyError, json.JSONDecodeError, ValidationError, ValueError) as error:
            raise RuntimeError(f"Content library failed schema validation: {error}") from error
        self.conditions = conditions
        self.preventive_items = preventive_items
        self.questions = questions

    def conditions_for_symptom(self, symptom_tag: str) -> list[ConditionEntry]:
        return [condition for condition in self.conditions if symptom_tag in condition.symptom_tags]

    def condition_by_id(self, condition_id: str) -> ConditionEntry | None:
        return next((condition for condition in self.conditions if condition.id == condition_id), None)

    def questions_for_symptom(self, symptom_tag: str) -> list[TriageQuestion]:
        return [question for question in self.questions if question.symptom_tag == symptom_tag]

    def filter_conditions(self, species=None, category=None, life_stage=None, symptom_tag=None):
        results = self.conditions
        if species:
            results = [item for item in results if item.species.value in (species, "both")]
        if category:
            results = [item for item in results if item.category.value == category]
        if life_stage:
            results = [item for item in results if life_stage in item.applicable_life_stages]
        if symptom_tag:
            results = [item for item in results if symptom_tag in item.symptom_tags]
        return results

    def filter_preventive(self, species=None, life_stage=None):
        results = self.preventive_items
        if species:
            results = [item for item in results if item.species.value in (species, "both")]
        if life_stage:
            results = [item for item in results if item.life_stage == life_stage]
        return results


content_library = ContentLibrary()
