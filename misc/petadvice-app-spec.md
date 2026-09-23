# PETAdvice — Product & Technical Specification (v0.1)

> Purpose of this document: a build-ready brief for PETAdvice — an app that helps cat and dog owners recognize common, often-treatable-at-home problems, apply preventive care by age/environment, and judge when it's actually time to see a vet. Written to be handed to a coding agent (e.g. Claude Code) as the source of truth while scaffolding the project. Update it as decisions change — it's a living spec, not a one-time brief.

---

## 1. Vision & Positioning

PETAdvice is a **first point of reference** for pet owners — not a diagnostic tool, not a replacement for a vet. Its job is to help an owner:
1. Understand what's likely going on with a symptom, in plain language.
2. Know what's safe to monitor at home vs. what needs a vet, and how urgently.
3. Follow age- and environment-appropriate preventive care so fewer problems happen in the first place.

**Non-goal:** this is explicitly not an app that diagnoses a named condition for a specific animal. That line is both a legal boundary (see §2) and a product-design boundary — every feature decision should be checked against it.

---

## 2. Legal & Regulatory Guardrails (read this before building anything)

These are hard constraints, not style suggestions. An agent building any triage, content, or copy feature must respect them.

- **Ireland — Veterinary Practice Act 2005**: the practice of veterinary medicine is legally defined to include *diagnosing* an animal's disease, injury, pain, deformity or state of health, and *giving advice following such a diagnosis* as to the care required. Both are reserved to registered veterinary practitioners. PETAdvice must not present output as a diagnosis of a specific animal's condition.
- **Veterinary Council of Ireland (VCI) clarification**: telemedicine may be used for **triage or general, non-specific advice**, but cannot replace a physical examination. This is the lane PETAdvice should live in — urgency bands and general guidance, not condition-specific diagnosis.
- **Veterinary nurses vs. veterinary surgeons**: a registered Veterinary Nurse (like your wife) is a real asset for content drafting, plain-language QA, and catching errors — but in Ireland/UK-style regulation, veterinary nurses have a narrower scope of practice than veterinary surgeons and generally can't diagnose or prescribe independently. For content credibility and legal safety, treat her as your primary internal reviewer, but route final sign-off on anything diagnosis-adjacent through a registered veterinary surgeon before it ships.
- **EU expansion**: veterinary regulation is set nationally. Rules that work in Ireland are not guaranteed to transfer to another EU market — re-verify per country before launching there, don't assume.
- **GDPR**: owner accounts hold personal data (name, email, location). Pet health data isn't personal data of a human, but plan lawful basis, consent, retention, and deletion from day one rather than retrofitting.
- **Product copy rule of thumb**: outputs should read as "urgency + general guidance," e.g. *"Repeated vomiting with blood can indicate a serious problem — see a vet within 24 hours,"* never *"Your dog has gastroenteritis."*

**Concrete implementation checks for any triage feature:**
- [ ] Does the output name a specific likely diagnosis? → Not allowed. Rephrase as urgency + general guidance.
- [ ] Is `home_care_guidance` populated for anything above `monitor_home` urgency? → Should be null; a vet-referral case gets referral guidance, not home treatment steps.
- [ ] Has every `red_flags` entry been checked by a vet reviewer? → Required before content ships.

---

## 3. Content Architecture

### 3.1 Species & entry types
Two entry types per species (dog / cat, mostly not shared): **problem/symptom entries** (reactive) and **preventive care entries** (proactive). Life stage and environment are filtering dimensions on both.

### 3.2 Life stages

Use the current professional-consensus bands — this keeps content defensible to a reviewing vet and avoids inventing arbitrary cutoffs.

**Dogs** (AAHA Canine Life Stage Guidelines) — bands are breed/size-dependent:

| Stage | Age range |
|---|---|
| Puppy | Birth → 6–9 months (varies by breed/size) |
| Young adult | 6–9 months → 3–4 years |
| Mature adult | 3–4 years → start of last 25% of estimated lifespan (breed/size-dependent) |
| Senior | Last 25% of estimated lifespan → end of life |

A Great Dane can enter "senior" around 6; a small terrier may not until 10+. Estimating this needs a breed-size lookup, not just a birthdate (see `life_stage` property on the `Pet` model, §4).

**Cats** (AAHA/AAFP Feline Life Stage Guidelines):

| Stage | Age range |
|---|---|
| Kitten | Birth → 1 year |
| Young adult | 1 → 6 years |
| Mature adult | 7 → 10 years |
| Senior | 10+ years |

(A more granular consumer-facing breakdown — kitten 0–6mo, junior 6mo–2yr, adult 3–7yr, mature 7–10yr, senior 11–14yr, geriatric 15+ — is also in common use if you want finer content tiers later.)

### 3.3 Problem/symptom category taxonomy (body-system based)

`gastrointestinal` · `dermatological` · `musculoskeletal` · `dental_oral` · `ear_eye` · `respiratory` · `urinary_reproductive` · `parasites` · `behavioral` · `weight_nutrition` · `emergency_trauma` (cross-cutting; always overrides normal urgency)

### 3.4 Environment & lifestyle factors (the differentiator)

`indoor_only` / `outdoor_access` · `multi_pet_household` · `urban` / `rural` · `seasonal_summer` / `seasonal_winter` · `breed_predisposed`

Indoor vs. outdoor access is the single biggest risk-profile split for cats (outdoor: trauma, infectious disease, parasites, fights; indoor: obesity, dental disease, stress). This dimension is where "prophylactic measures tied to environment" actually gets built, and it's underused by competitor apps — worth prioritizing.

### 3.5 Urgency levels (what the triage engine outputs)

`monitor_home` → `vet_soon` (within a few days) → `vet_24h` (within 24 hours) → `emergency_now` (immediate)

---

## 4. Data Schema

Pydantic models (fits your FastAPI stack directly and doubles as documentation). Treat this as the seed schema — refine field names as real content surfaces edge cases.

```python
from enum import Enum
from typing import Optional
from datetime import date, datetime
from pydantic import BaseModel, Field


# --- Controlled vocabularies -------------------------------------------

class Species(str, Enum):
    dog = "dog"
    cat = "cat"
    both = "both"

class DogLifeStage(str, Enum):
    puppy = "puppy"                 # birth – 6-9mo (breed/size dependent)
    young_adult = "young_adult"     # 6-9mo – 3-4yr
    mature_adult = "mature_adult"   # 3-4yr – start of last 25% of lifespan
    senior = "senior"               # last 25% of lifespan – EOL

class CatLifeStage(str, Enum):
    kitten = "kitten"               # birth – 1yr
    young_adult = "young_adult"     # 1-6yr
    mature_adult = "mature_adult"   # 7-10yr
    senior = "senior"               # 10yr+

class BreedSize(str, Enum):
    small = "small"     # roughly <10kg adult weight
    medium = "medium"   # 10-25kg
    large = "large"     # 25-40kg
    giant = "giant"     # 40kg+

class Category(str, Enum):
    gastrointestinal = "gastrointestinal"
    dermatological = "dermatological"
    musculoskeletal = "musculoskeletal"
    dental_oral = "dental_oral"
    ear_eye = "ear_eye"
    respiratory = "respiratory"
    urinary_reproductive = "urinary_reproductive"
    parasites = "parasites"
    behavioral = "behavioral"
    weight_nutrition = "weight_nutrition"
    emergency_trauma = "emergency_trauma"

class EnvironmentFactor(str, Enum):
    indoor_only = "indoor_only"
    outdoor_access = "outdoor_access"
    multi_pet_household = "multi_pet_household"
    urban = "urban"
    rural = "rural"
    seasonal_summer = "seasonal_summer"
    seasonal_winter = "seasonal_winter"
    breed_predisposed = "breed_predisposed"

class UrgencyLevel(str, Enum):
    monitor_home = "monitor_home"
    vet_soon = "vet_soon"
    vet_24h = "vet_24h"
    emergency_now = "emergency_now"


# --- Core entities -------------------------------------------------------

class Pet(BaseModel):
    id: str
    owner_id: str
    name: str
    species: Species
    breed: Optional[str] = None
    breed_size: Optional[BreedSize] = None
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    neutered: Optional[bool] = None
    weight_kg: Optional[float] = None
    environment_factors: list[EnvironmentFactor] = []
    known_conditions: list[str] = []

    # computed, not stored: derive from dob + species + breed_size
    # against the life-stage tables in §3.2
    def life_stage(self) -> str:
        raise NotImplementedError


class RedFlag(BaseModel):
    description: str
    escalates_to: UrgencyLevel = UrgencyLevel.emergency_now


class ConditionEntry(BaseModel):
    id: str
    name: str
    species: Species
    category: Category
    applicable_life_stages: list[str]        # DogLifeStage/CatLifeStage values
    environment_factors: list[EnvironmentFactor] = []
    breed_predispositions: list[str] = []
    symptom_tags: list[str]                   # links into the triage flow
    urgency_default: UrgencyLevel
    red_flags: list[RedFlag] = []
    home_care_guidance: Optional[str] = None  # populate ONLY if urgency_default == monitor_home
    prevention_tips: Optional[str] = None
    vet_reviewed_by: Optional[str] = None
    last_reviewed_date: Optional[date] = None
    sources: list[str] = []                   # citation to guideline body/document


class TriageQuestion(BaseModel):
    id: str
    prompt: str
    symptom_tag: str
    options: list[str]
    escalate_if: dict[str, UrgencyLevel] = {}  # option text -> urgency override


class TriageSession(BaseModel):
    id: str
    pet_id: str
    started_at: datetime
    symptom_entry_point: str
    answers: dict[str, str] = {}
    resulting_urgency: Optional[UrgencyLevel] = None
    resulting_guidance: Optional[str] = None
    condition_entries_matched: list[str] = []


class PreventiveCareItem(BaseModel):
    id: str
    species: Species
    life_stage: str
    title: str
    description: str
    recurrence: Optional[str] = None      # e.g. "annual", "every 3 months"
    trigger_age_days: Optional[int] = None
    sources: list[str] = []
```

### 4.1 Worked examples

Two fully populated entries, chosen to demonstrate both ends of the urgency scale. **The `sources` fields are placeholders** — real entries need a genuine citation (guideline document + section) added during content authoring, not left generic.

```json
{
  "id": "dog-gi-001",
  "name": "Acute vomiting, isolated episode",
  "species": "dog",
  "category": "gastrointestinal",
  "applicable_life_stages": ["young_adult", "mature_adult"],
  "environment_factors": [],
  "breed_predispositions": [],
  "symptom_tags": ["vomiting"],
  "urgency_default": "monitor_home",
  "red_flags": [
    {"description": "Repeated vomiting (3+ times in a few hours)", "escalates_to": "vet_24h"},
    {"description": "Blood in vomit", "escalates_to": "emergency_now"},
    {"description": "Distended/bloated abdomen with unproductive retching", "escalates_to": "emergency_now"},
    {"description": "Known access to toxins, foreign objects, or chocolate", "escalates_to": "vet_24h"}
  ],
  "home_care_guidance": "Withhold food for a few hours, offer small amounts of water, and reintroduce a bland diet gradually if there's no further vomiting. Contact a vet if it recurs or your dog seems unwell.",
  "prevention_tips": "Secure bins, supervise access to human food, and transition between diets gradually.",
  "vet_reviewed_by": null,
  "last_reviewed_date": null,
  "sources": ["<guideline citation to add during content authoring>"]
}
```

```json
{
  "id": "cat-urinary-001",
  "name": "Straining to urinate / suspected urinary blockage",
  "species": "cat",
  "category": "urinary_reproductive",
  "applicable_life_stages": ["young_adult", "mature_adult", "senior"],
  "environment_factors": ["indoor_only", "multi_pet_household"],
  "breed_predispositions": [],
  "symptom_tags": ["straining_to_urinate", "frequent_litter_visits", "vocalizing_in_litter_box"],
  "urgency_default": "emergency_now",
  "red_flags": [
    {"description": "Male cat straining with little or no urine produced", "escalates_to": "emergency_now"}
  ],
  "home_care_guidance": null,
  "prevention_tips": "Multiple clean litter trays, a wet-food-inclusive diet, and reducing multi-cat household stress can lower recurrence risk.",
  "vet_reviewed_by": null,
  "last_reviewed_date": null,
  "sources": ["<guideline citation to add during content authoring>"]
}
```

The second example matters disproportionately: a male cat straining to urinate with little/no output is one of the most time-critical true emergencies in companion-animal medicine (urethral obstruction). This is exactly the kind of entry where you want your wife's review before it ever ships — getting the `urgency_default` and `red_flags` right here matters more than almost anything else in the content library.

---

## 5. Feature Scope

**MVP**
- Pet profile (species, breed, DOB, weight, environment factors, neuter status)
- Structured triage flow (multiple-choice, not free-text/AI symptom parsing — safer and easier to keep medically defensible) → urgency band + guidance
- Browsable condition & symptom library, filterable by species/life stage/category
- Preventive care calendar: vaccination/deworming/dental/parasite-prevention reminders, driven by life stage + environment
- Always-visible emergency red-flag list per species, independent of the triage flow

**Phase 2**
- Native app wrapper (once content + triage logic are validated via PWA/web)
- Accounts, push notifications for preventive care reminders
- Multi-pet household support

**Phase 3 (adds real liability surface — don't rush into these)**
- Ask-a-vet chat (needs licensed staffing)
- Photo-based symptom input
- Portuguese localization (a genuine market angle given your background, worth revisiting once EN content is solid)

---

## 6. Triage Flow Logic

Keep it a structured decision tree, not open-ended AI interpretation — it's safer, cheaper to build, easier for a vet to review end-to-end, and easier to defend if ever questioned.

```
1. Owner selects species + picks/searches a symptom (symptom_tag)
2. Engine loads all ConditionEntry rows matching (species, symptom_tag)
3. Owner answers a short set of TriageQuestion items tied to that symptom_tag
4. For each answer, check escalate_if — if matched, raise resulting_urgency
5. Check pet's environment_factors and life_stage against each candidate
   ConditionEntry's red_flags — any hit escalates urgency further
6. Final resulting_urgency = highest urgency triggered across all checks
7. Return resulting_guidance:
   - monitor_home  → home_care_guidance text
   - vet_soon/vet_24h/emergency_now → referral guidance only, no home-care text
```

Urgency only ever escalates during a session, never de-escalates — a session should never talk a worried owner down from a red flag.

---

## 7. API Surface (FastAPI sketch)

```
GET    /pets/{pet_id}
POST   /pets
GET    /conditions?species=&category=&life_stage=&symptom_tag=
GET    /conditions/{id}
POST   /triage/start                  { pet_id, symptom_tag }
POST   /triage/{session_id}/answer    { question_id, answer }
GET    /triage/{session_id}/result
GET    /preventive-care?species=&life_stage=
```

---

## 8. Content Sourcing & Review Process

Anchor content to named, citable veterinary guideline bodies rather than general web content — this is both an accuracy requirement and your credibility differentiator ("vet-reviewed, guideline-based" vs. competitors' generic AI output):

- **WSAVA** (World Small Animal Veterinary Association) — free, peer-reviewed global guidelines: vaccination, nutrition, pain management, dental disease.
- **AAHA/AAFP** — life-stage guidelines (used above) plus condition-specific guidelines.
- **ISFM** (International Society of Feline Medicine) — cat-specific guidelines, including environmental needs.
- **ESCCAP** (European Scientific Counsel Companion Animal Parasites) — EU-focused, useful for the parasite-prevention/seasonal content specifically.

**Review workflow:**
1. Draft entry against a named source, populate `sources`.
2. First-pass review by your wife (RVN) — plain-language accuracy, catches errors, flags anything that reads as diagnostic rather than general.
3. Final clinical sign-off by a registered veterinary surgeon on anything in `emergency_trauma`, `urinary_reproductive`, or any entry whose `urgency_default` is `emergency_now` or `vet_24h` — these are the highest-stakes entries.
4. Set `vet_reviewed_by` and `last_reviewed_date` only once both passes are done.
5. Re-review content periodically — guidelines get updated (e.g. WSAVA's vaccination guidelines have had multiple revisions); track a review cadence per entry, not just at launch.

---

## 9. Tech Stack Recommendation

- **Backend**: FastAPI (Python) — matches your existing experience, fast to iterate on the triage/content API.
- **MVP delivery**: PWA / responsive web first, before native iOS/Android — cheaper to validate content quality and triage logic before app-store submission (which will scrutinize medical-adjacent content) and before maintaining two codebases.
- **Data**: relational DB is fine for structured content (Postgres); content entries could also live as versioned JSON/YAML files in-repo initially, which makes vet review via pull request genuinely easy — worth considering for v0 before a full CMS is justified.
- **Personal data**: plan GDPR-compliant storage/consent/retention for owner accounts from the start.

---

## 10. Suggested Project Structure

```
petadvice/
├── app/
│   ├── main.py
│   ├── models/               # Pydantic models from §4 (schema.py)
│   ├── api/
│   │   ├── pets.py
│   │   ├── conditions.py
│   │   ├── triage.py
│   │   └── preventive_care.py
│   ├── content/               # condition_entries/*.json, preventive_care/*.json
│   ├── services/
│   │   ├── triage_engine.py
│   │   └── life_stage_calculator.py
│   └── db/
├── tests/
└── content_review/            # review checklist + sign-off log (ties to §8 workflow)
```

---

## 11. Roadmap

- **Phase 0 — Content foundation**: build and vet-review a first batch of condition entries and preventive care items (offline, before app code) to validate the schema holds up against real content, not just the two worked examples above.
- **Phase 1 — MVP**: FastAPI backend + PWA, structured triage flow, browsable library, preventive care calendar.
- **Phase 2 — Native app**: wrap the validated MVP, add accounts/notifications/multi-pet.
- **Phase 3 — Expansion**: ask-a-vet, photo input, additional markets/languages — each of these adds real liability surface, so revisit the legal guardrails in §2 before building any of them.

---

## 12. Open Decisions (not blocking, but worth deciding soon)

- [ ] Native app first vs. staying PWA longer
- [ ] Which EU markets beyond Ireland to target at launch, and re-verifying regulation per market
- [ ] Monetization tier boundaries (what's free vs. paid)
- [ ] Whether ask-a-vet (Phase 3) uses your wife, contracted vets, or a partnered clinic
- [ ] Relationship to the separate pet-products dropshipping store idea — kept fully separate, or cross-linked for content marketing/affiliate
