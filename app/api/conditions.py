from fastapi import APIRouter, HTTPException, Request

from app.content.loader import content_library
from app.i18n import request_language

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("")
def list_conditions(request: Request, species: str | None = None, category: str | None = None, life_stage: str | None = None, symptom_tag: str | None = None):
    language = request_language(request)
    return [_with_related_care(item, species, language) for item in content_library.filter_conditions(species, category, life_stage, symptom_tag, language)]


@router.get("/{condition_id}")
def get_condition(condition_id: str, request: Request):
    condition = content_library.condition_by_id(condition_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    language = request_language(request)
    return _with_related_care(content_library.localize_condition(condition, language), None, language)


def _with_related_care(condition, species: str | None, language: str) -> dict:
    items = content_library.related_care(condition, species, language)
    return condition.model_dump(mode="json") | {"related_care_items": [item.model_dump(mode="json", include={"id", "title", "description", "recurrence"}) for item in items]}
