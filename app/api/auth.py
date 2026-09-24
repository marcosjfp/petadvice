from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse)
def signup(payload: OwnerSignup, db: Session = Depends(get_session)):
    existing = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists")
    owner = Owner(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        consent_given_at=datetime.now(timezone.utc),
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return TokenResponse(access_token=create_access_token(owner.id))


@router.post("/login", response_model=TokenResponse)
def login(payload: OwnerLogin, db: Session = Depends(get_session)):
    owner = db.exec(select(Owner).where(Owner.email == payload.email)).first()
    if owner is None or not verify_password(payload.password, owner.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return TokenResponse(access_token=create_access_token(owner.id))


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
    return {"status": "account and all associated data deleted"}
