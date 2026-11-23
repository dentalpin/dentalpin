"""Fixed destinations with versioned, clinic-controlled wording."""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.modules.patients.schemas import PatientAddress

Channel = Literal["whatsapp", "sms", "email"]
Purpose = Literal["whatsapp", "sms", "email", "appointment_reminder"]
PURPOSES: tuple[Purpose, ...] = ("whatsapp", "sms", "email", "appointment_reminder")
ContactField = Literal[
    "first_name",
    "last_name",
    "date_of_birth",
    "phone",
    "email",
    "address",
    "national_id",
    "national_id_type",
    "preferred_language",
]
ContextField = Literal[
    "is_pregnant",
    "pregnancy_week",
    "is_lactating",
    "is_on_anticoagulants",
    "anticoagulant_medication",
    "is_smoker",
    "smoking_frequency",
    "alcohol_consumption",
    "bruxism",
    "adverse_reactions_to_anesthesia",
    "anesthesia_reaction_details",
]
Index = Annotated[int, Field(ge=0, le=49)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
Answer = bool | Literal["unknown", "prefer_not_to_answer"]


class IntakeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FormDefinition(IntakeInput):
    version: int = Field(ge=1, le=2_147_483_647)
    locale: str = Field(pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    questionnaire_intro: Text
    question_labels: dict[
        ContactField | ContextField | Literal["allergies", "medications", "diseases", "surgeries"],
        Text,
    ] = Field(default_factory=dict)
    privacy_notice: Text
    consent_texts: dict[Purpose, Text]
    enabled_channels: set[Channel] = Field(default_factory=lambda: {"whatsapp", "email"})

    @model_validator(mode="after")
    def require_all_texts(self):
        if set(self.consent_texts) != set(PURPOSES):
            raise ValueError("Provide a text for each communication choice")
        return self


class RetentionConfig(IntakeInput):
    clinical_years: int = Field(default=5, ge=5, le=100)
    communications_years_after_withdrawal: int = Field(default=3, ge=1, le=100)
    discarded_days: int = Field(default=30, ge=1, le=3650)
    unsigned_hours: int = Field(default=24, ge=1, le=720)


class Representative(IntakeInput):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    relationship: Literal["guardian", "representative"]


class ContactAnswers(IntakeInput):
    first_name: Name | None = None
    last_name: Name | None = None
    date_of_birth: date | None = None
    phone: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    address: PatientAddress | None = None
    national_id: str | None = Field(default=None, max_length=50)
    national_id_type: Literal["dni", "nie", "passport"] | None = None
    preferred_language: str | None = Field(default=None, min_length=2, max_length=10)


class ContextAnswers(IntakeInput):
    is_pregnant: Answer | None = None
    pregnancy_week: int | None = Field(default=None, ge=1, le=42)
    is_lactating: Answer | None = None
    is_on_anticoagulants: Answer | None = None
    anticoagulant_medication: Name | None = None
    is_smoker: Answer | None = None
    smoking_frequency: Name | None = None
    alcohol_consumption: Name | None = None
    bruxism: Answer | None = None
    adverse_reactions_to_anesthesia: Answer | None = None
    anesthesia_reaction_details: str | None = Field(default=None, max_length=500)


class AllergyAnswer(IntakeInput):
    name: Name
    reaction: str | None = Field(default=None, max_length=500)


class MedicationAnswer(IntakeInput):
    name: Name
    dosage: Name | None = None
    frequency: Name | None = None


class DiseaseAnswer(IntakeInput):
    name: Name
    diagnosis_date: date | None = None


class SurgeryAnswer(IntakeInput):
    procedure: str = Field(min_length=1, max_length=200)
    surgery_date: date | None = None
    complications: str | None = Field(default=None, max_length=2000)


class HealthAnswers(IntakeInput):
    no_known_history: Answer | None = None
    context: ContextAnswers = Field(default_factory=ContextAnswers)
    allergies: list[AllergyAnswer] = Field(default_factory=list, max_length=50)
    medications: list[MedicationAnswer] = Field(default_factory=list, max_length=50)
    diseases: list[DiseaseAnswer] = Field(default_factory=list, max_length=50)
    surgeries: list[SurgeryAnswer] = Field(default_factory=list, max_length=50)


class SignedAnswers(IntakeInput):
    contact: ContactAnswers
    health: HealthAnswers
    acknowledged_notice: Literal[True]
    choices: dict[Purpose, bool]

    @model_validator(mode="after")
    def require_all_choices(self):
        if set(self.choices) != set(PURPOSES):
            raise ValueError("Record each communication choice")
        return self


class AdministrativeReview(IntakeInput):
    fields: set[ContactField] = Field(default_factory=set)
    apply_choices: bool = False
    verified_channels: set[Channel] = Field(default_factory=set)


class DiseaseReview(IntakeInput):
    is_controlled: bool
    is_critical: bool


class ClinicalReview(IntakeInput):
    fields: set[ContextField] = Field(default_factory=set)
    allergies: dict[Index, Literal["low", "medium", "high", "critical"]] = Field(
        default_factory=dict
    )
    medications: set[Index] = Field(default_factory=set)
    diseases: dict[Index, DiseaseReview] = Field(default_factory=dict)
    surgeries: set[Index] = Field(default_factory=set)
