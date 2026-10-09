from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import (
    Owner,
    OwnerLogin,
    OwnerPublic,
    OwnerSignup,
    Pet,
    TokenResponse,
    TriageSession,
)
from app.services.auth import (
    create_access_token,
    get_current_owner,
    hash_password,
    verify_password,
    verify_dummy_password,
    set_session_cookie,
    clear_session_cookie,
    verify_auth_origin,
)

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(verify_auth_origin)])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: OwnerSignup, response: Response, db: Session = Depends(get_session)):
    existing = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    owner = Owner(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(owner)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=400, detail="An account with this email already exists") from error
    db.refresh(owner)
    token = create_access_token(owner.id)
    set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse)
def login(payload: OwnerLogin, response: Response, db: Session = Depends(get_session)):
    owner = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if owner is None:
        verify_dummy_password(payload.password)
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if owner.hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
        owner.hashed_password = hash_password(payload.password)
        db.add(owner)
        db.commit()
    token = create_access_token(owner.id)
    set_session_cookie(response, token)
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"status": "logged out"}


@router.get("/me", response_model=OwnerPublic)
def read_current_owner(current_owner: Owner = Depends(get_current_owner)):
    return current_owner


@router.get("/me/export")
def export_my_data(
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    pet_ids = [pet.id for pet in pets]
    sessions = (
        db.exec(select(TriageSession).where(TriageSession.pet_id.in_(pet_ids))).all()
        if pet_ids
        else []
    )
    return {
        "owner": current_owner.model_dump(exclude={"hashed_password"}),
        "pets": [pet.model_dump() for pet in pets],
        "triage_sessions": [session.model_dump() for session in sessions],
    }


@router.delete("/me")
def delete_my_account(
    response: Response,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    for pet in pets:
        sessions = db.exec(select(TriageSession).where(TriageSession.pet_id == pet.id)).all()
        for session in sessions:
            db.delete(session)
        db.delete(pet)
    db.delete(current_owner)
    db.commit()
    clear_session_cookie(response)
    return {"status": "account and all associated data deleted"}
