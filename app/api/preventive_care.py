from fastapi import APIRouter, Request

from app.content.loader import content_library
from app.i18n import request_language

router = APIRouter(prefix="/preventive-care", tags=["preventive-care"])


@router.get("")
def list_preventive_care(request: Request, species: str | None = None, life_stage: str | None = None):
    return content_library.filter_preventive(species, life_stage, request_language(request))
