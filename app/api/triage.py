from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.content.loader import content_library
from app.db import get_session
from app.models.schema import Owner, Pet, TriageAnswerRequest, TriageSession, TriageStartRequest
from app.services import triage_engine
from app.services.auth import get_optional_owner

router = APIRouter(prefix="/triage", tags=["triage"])


def _get_owned_pet(db: Session, pet_id: str, owner: Owner) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None or pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


def _verify_session_ownership(db: Session, session_id: str, owner: Owner | None) -> None:
    session = db.get(TriageSession, session_id)
    pet = db.get(Pet, session.pet_id) if session else None
    if session is None or pet is None:
        raise HTTPException(status_code=404, detail="Triage session not found")
    if owner is None and pet.owner_id is not None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if owner is not None and pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Triage session not found")


@router.get("/questions")
def get_triage_questions(symptom_tag: str):
    """Return the full question tree for content review tooling."""
    return content_library.questions_for_symptom(symptom_tag)


@router.post("/start")
def start_triage(
    payload: TriageStartRequest,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    if payload.pet_id is None:
        if current_owner is not None:
            raise HTTPException(status_code=422, detail="pet_id is required for an account check")
        pet = Pet(name="Guest pet", species=payload.species)
        db.add(pet)
        db.commit()
        db.refresh(pet)
    else:
        if current_owner is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        pet = _get_owned_pet(db, payload.pet_id, current_owner)
    session, first_question = triage_engine.start_session(db, pet, payload.symptom_tag)
    return {"session_id": session.id, "next_question": first_question, "flow_complete": first_question is None}


@router.post("/{session_id}/answer")
def answer_triage(
    session_id: str,
    payload: TriageAnswerRequest,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner)
    try:
        _, next_question, flow_complete = triage_engine.answer_question(db, session_id, payload)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    except triage_engine.InvalidAnswerError:
        raise HTTPException(status_code=422, detail="Answer is not valid for this question")
    return {"next_question": next_question, "flow_complete": flow_complete}


@router.get("/{session_id}/result")
def get_triage_result(
    session_id: str,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner)
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
