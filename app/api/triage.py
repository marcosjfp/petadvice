from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.content.loader import content_library
from app.db import get_session
from app.models.schema import Pet, TriageAnswerRequest, TriageStartRequest
from app.services import triage_engine

router = APIRouter(prefix="/triage", tags=["triage"])


@router.get("/questions")
def get_triage_questions(symptom_tag: str):
    return content_library.questions_for_symptom(symptom_tag)


@router.post("/start")
def start_triage(payload: TriageStartRequest, db: Session = Depends(get_session)):
    pet = db.get(Pet, payload.pet_id)
    if pet is None:
        raise HTTPException(status_code=404, detail="Pet not found")
    return {"session_id": triage_engine.start_session(db, pet, payload.symptom_tag).id}


@router.post("/{session_id}/answer")
def answer_triage(session_id: str, payload: TriageAnswerRequest, db: Session = Depends(get_session)):
    try:
        triage_engine.answer_question(db, session_id, payload)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    except triage_engine.InvalidAnswerError:
        raise HTTPException(status_code=422, detail="Answer is not valid for this question")
    return {"status": "recorded"}


@router.get("/{session_id}/result")
def get_triage_result(session_id: str, db: Session = Depends(get_session)):
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
