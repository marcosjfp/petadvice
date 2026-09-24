from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models.schema import Owner, Pet, PetCreate
from app.services.auth import get_current_owner
from app.services.life_stage_calculator import calculate_life_stage

router = APIRouter(prefix="/pets", tags=["pets"])


@router.post("", response_model=Pet)
def create_pet(
    payload: PetCreate,
    current_owner: Owner = Depends(get_current_owner),
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
    return pet


@router.get("/{pet_id}")
def get_pet(
    pet_id: str,
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pet = db.get(Pet, pet_id)
    if pet is None or pet.owner_id != current_owner.id:
        raise HTTPException(status_code=404, detail="Pet not found")
    return {**pet.model_dump(), "life_stage": calculate_life_stage(pet)}


@router.get("")
def list_my_pets(
    current_owner: Owner = Depends(get_current_owner),
    db: Session = Depends(get_session),
):
    pets = db.exec(select(Pet).where(Pet.owner_id == current_owner.id)).all()
    return [{**pet.model_dump(), "life_stage": calculate_life_stage(pet)} for pet in pets]
