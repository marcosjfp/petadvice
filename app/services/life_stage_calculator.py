from datetime import date

from app.models.schema import BreedSize, CatLifeStage, DogLifeStage, Pet, Species


def _age_years(dob: date, as_of: date | None = None) -> float:
    return ((as_of or date.today()) - dob).days / 365.25


_DOG_THRESHOLDS: dict[BreedSize, tuple[float, float, float]] = {
    BreedSize.small: (1.0, 3.5, 10.0),
    BreedSize.medium: (0.75, 3.5, 9.0),
    BreedSize.large: (0.75, 3.0, 7.5),
    BreedSize.giant: (0.5, 2.5, 6.0),
}
_CAT_THRESHOLDS = (1.0, 7.0, 10.0)


def calculate_dog_life_stage(dob: date, breed_size: BreedSize | None) -> DogLifeStage:
    puppy_end, mature_start, senior_start = _DOG_THRESHOLDS[breed_size or BreedSize.medium]
    age = _age_years(dob)
    if age < puppy_end:
        return DogLifeStage.puppy
    if age < mature_start:
        return DogLifeStage.young_adult
    if age < senior_start:
        return DogLifeStage.mature_adult
    return DogLifeStage.senior


def calculate_cat_life_stage(dob: date) -> CatLifeStage:
    age = _age_years(dob)
    if age < _CAT_THRESHOLDS[0]:
        return CatLifeStage.kitten
    if age < _CAT_THRESHOLDS[1]:
        return CatLifeStage.young_adult
    if age < _CAT_THRESHOLDS[2]:
        return CatLifeStage.mature_adult
    return CatLifeStage.senior


def calculate_life_stage(pet: Pet) -> str | None:
    if pet.date_of_birth is None:
        return None
    if pet.species == Species.dog:
        return calculate_dog_life_stage(pet.date_of_birth, pet.breed_size).value
    if pet.species == Species.cat:
        return calculate_cat_life_stage(pet.date_of_birth).value
    return None
