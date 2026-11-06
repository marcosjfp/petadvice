from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import GuestAccess, Owner, Pet, PetCreate, PetUpdate, TriageSession
from app.services.auth import get_current_owner, require_recent_owner, require_verified_owner, verify_auth_origin
from app.services.life_stage_calculator import calculate_life_stage

router = APIRouter(prefix="/pets", tags=["pets"], dependencies=[Depends(verify_auth_origin)])
SPECIES_IMMUTABLE = "Species cannot be changed after a pet profile is created"


def pet_response(pet: Pet):
    return {**pet.model_dump(), "life_stage": calculate_life_stage(pet)}


def owned_pet(db: Session, pet_id: str, owner: Owner) -> Pet:
    pet = db.get(Pet, pet_id)
    # Another owner's pet is indistinguishable from a missing one.
    if pet is None or pet.owner_id != owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet


@router.post("")
def create_pet(
    payload: PetCreate,
    current_owner: Owner = Depends(require_verified_owner),
    db: Session = Depends(get_session),
):
    pet = Pet(
        owner_id=current_owner.id,
        **payload.model_dump(exclude={"environment_factors"}),
        environment_factors=[item.value for item in payload.environment_factors],
    )
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet_response(pet)


@router.get("/{pet_id}")
def get_pet(
    pet_id: str,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    return pet_response(owned_pet(db, pet_id, current_owner))


@router.patch("/{pet_id}")
def update_pet(
    pet_id: str,
    payload: PetUpdate,
    current_owner: Owner = Depends(require_verified_owner),
    db: Session = Depends(get_session),
):
    pet = owned_pet(db, pet_id, current_owner)
    changes = payload.model_dump(exclude_unset=True)
    species = changes.pop("species", None)
    if species is not None and species != pet.species:
        raise HTTPException(status_code=422, detail=SPECIES_IMMUTABLE)
    if "environment_factors" in changes:
        changes["environment_factors"] = [item.value for item in payload.environment_factors or []]
    for field, value in changes.items():
        setattr(pet, field, value)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet_response(pet)


@router.delete("/{pet_id}")
def delete_pet(
    pet_id: str,
    current_owner: Owner = Depends(require_recent_owner),
    db: Session = Depends(get_session),
):
    pet = owned_pet(db, pet_id, current_owner)
    for session in db.exec(select(TriageSession).where(TriageSession.pet_id == pet.id)).all():
        guest = db.get(GuestAccess, session.id)
        if guest:
            db.delete(guest)
            db.flush()
        db.delete(session)
    db.flush()
    db.delete(pet)
    db.commit()
    return {"status": "pet profile and its checks deleted"}


@router.get("")
def list_my_pets(
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    return [pet_response(pet) for pet in pets]
