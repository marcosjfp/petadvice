import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.content.loader import content_library
from app.db import get_session
from app.models.schema import GuestAccess, Owner, Pet, TriageAnswerRequest, TriageSession, TriageStartRequest
from app.services import triage_engine
from app.services.auth import as_utc, get_current_owner, get_optional_owner, utcnow, verify_auth_origin
from app.services.account_actions import token_hash
from app.services.rate_limit import limit_requests
from app.settings import get_settings

router = APIRouter(prefix="/triage", tags=["triage"], dependencies=[Depends(verify_auth_origin)])


def _get_owned_pet(db: Session, pet_id: str, owner: Owner) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None or pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


def _verify_session_ownership(db: Session, session_id: str, owner: Owner | None, request: Request) -> None:
    session = db.get(TriageSession, session_id)
    pet = db.get(Pet, session.pet_id) if session else None
    if session is None or pet is None:
        raise HTTPException(status_code=404, detail="Triage session not found")
    if pet.owner_id is None:
        access = db.get(GuestAccess, session_id)
        token = request.headers.get('x-guest-token', '')
        if not access or as_utc(access.expires_at) <= utcnow() or not secrets.compare_digest(token_hash(token), access.token_hash):
            raise HTTPException(404, 'Triage session not found or expired')
        return
    if owner is None and pet.owner_id is not None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if owner is not None and pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Triage session not found")


@router.get("/questions")
def get_triage_questions(symptom_tag: str):
    """Return the full question tree for content review tooling."""
    return content_library.questions_for_symptom(symptom_tag)


@router.get('/history/{pet_id}')
def check_history(pet_id: str, before: str | None = None, owner: Owner = Depends(get_current_owner), db: Session = Depends(get_session)):
    _get_owned_pet(db, pet_id, owner)
    query = select(TriageSession).where(TriageSession.pet_id == pet_id)
    if before:
        # Cursor is a check ID scoped to this pet, not an unbounded offset.
        anchor = db.get(TriageSession, before)
        if anchor is None or anchor.pet_id != pet_id:
            raise HTTPException(404, 'Check not found')
        query = query.where((TriageSession.started_at < anchor.started_at) | ((TriageSession.started_at == anchor.started_at) & (TriageSession.id < anchor.id)))
    rows = db.exec(query.order_by(TriageSession.started_at.desc(), TriageSession.id.desc()).limit(21)).all()
    return {'checks': [{'session_id': row.id, 'started_at': as_utc(row.started_at), 'symptom': row.symptom_entry_point, 'complete': row.current_question_id is None, 'urgency': row.resulting_urgency} for row in rows[:20]], 'next_cursor': rows[19].id if len(rows) > 20 else None}


@router.post("/start", dependencies=[Depends(limit_requests('triage-start', '30/minute'))])
def start_triage(
    payload: TriageStartRequest,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    if not content_library.conditions_for_symptom(payload.symptom_tag) and not content_library.questions_for_symptom(payload.symptom_tag):
        raise HTTPException(status_code=422, detail="This symptom is not supported. Contact your veterinary practice for guidance.")
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
        if get_settings().email_verification_required and current_owner.email_verified_at is None:
            raise HTTPException(403, 'Verify your email before starting account checks')
    session, first_question = triage_engine.start_session(db, pet, payload.symptom_tag)
    guest_token = None
    expires_at = None
    if pet.owner_id is None:
        guest_token = secrets.token_urlsafe(32)
        expires_at = utcnow() + timedelta(hours=get_settings().guest_retention_hours)
        db.add(GuestAccess(session_id=session.id, token_hash=token_hash(guest_token), expires_at=expires_at))
        db.commit()
    return {"session_id": session.id, "next_question": first_question, "flow_complete": first_question is None, 'guest_token': guest_token, 'expires_at': expires_at}


@router.post("/{session_id}/answer", dependencies=[Depends(limit_requests('triage-answer', '120/minute'))])
def answer_triage(
    session_id: str,
    payload: TriageAnswerRequest,
    request: Request,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner, request)
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
    request: Request,
    current_owner: Owner | None = Depends(get_optional_owner),
    db: Session = Depends(get_session),
):
    _verify_session_ownership(db, session_id, current_owner, request)
    try:
        return triage_engine.compute_result(db, session_id)
    except triage_engine.UnknownSessionError:
        raise HTTPException(status_code=404, detail="Triage session not found")
    except triage_engine.IncompleteSessionError:
        raise HTTPException(status_code=409, detail="Complete the remaining questions before viewing guidance")


@router.get('/{session_id}/export')
def export_guest_check(session_id: str, request: Request, owner: Owner | None = Depends(get_optional_owner), db: Session = Depends(get_session)):
    _verify_session_ownership(db, session_id, owner, request)
    session = db.get(TriageSession, session_id)
    return {'pet': db.get(Pet, session.pet_id).model_dump(), 'triage_session': session.model_dump()}


@router.delete('/{session_id}')
def delete_guest_check(session_id: str, request: Request, owner: Owner | None = Depends(get_optional_owner), db: Session = Depends(get_session)):
    _verify_session_ownership(db, session_id, owner, request)
    session = db.get(TriageSession, session_id)
    pet = db.get(Pet, session.pet_id)
    if pet.owner_id is not None:
        raise HTTPException(403, 'Use account data controls to manage saved checks')
    db.delete(db.get(GuestAccess, session_id))
    db.flush()
    db.delete(session)
    db.flush()
    db.delete(pet)
    db.commit()
    return {'status': 'guest check deleted'}
