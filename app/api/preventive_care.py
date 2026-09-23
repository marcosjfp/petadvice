from fastapi import APIRouter

from app.content.loader import content_library

router = APIRouter(prefix="/preventive-care", tags=["preventive-care"])


@router.get("")
def list_preventive_care(species: str | None = None, life_stage: str | None = None):
    return content_library.filter_preventive(species, life_stage)
