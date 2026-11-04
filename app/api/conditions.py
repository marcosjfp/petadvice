from fastapi import APIRouter, HTTPException, Request

from app.content.loader import content_library
from app.i18n import request_language

router = APIRouter(prefix="/conditions", tags=["conditions"])


@router.get("")
def list_conditions(request: Request, species: str | None = None, category: str | None = None, life_stage: str | None = None, symptom_tag: str | None = None):
    return content_library.filter_conditions(species, category, life_stage, symptom_tag, request_language(request))


@router.get("/{condition_id}")
def get_condition(condition_id: str, request: Request):
    condition = content_library.condition_by_id(condition_id)
    if condition is None:
        raise HTTPException(status_code=404, detail="Condition not found")
    return content_library.localize_condition(condition, request_language(request))
