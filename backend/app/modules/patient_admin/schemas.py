"""Pydantic schemas for the patient_admin module."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

RELATIONSHIP_TYPES = {"parent", "child", "spouse", "sibling", "guardian", "ward", "other"}

# Inverse label shown on the *related* patient's page. Symmetric types map
# to themselves; parent/child and guardian/ward are true inverses.
INVERSE_RELATIONSHIP_TYPE = {
    "parent": "child",
    "child": "parent",
    "guardian": "ward",
    "ward": "guardian",
    "spouse": "spouse",
    "sibling": "sibling",
    "other": "other",
}


class PatientRelationshipCreate(BaseModel):
    related_patient_id: UUID
    relationship_type: str
    notes: str | None = None


class PatientRelationshipUpdate(BaseModel):
    notes: str | None = None


class PatientRelationshipResponse(BaseModel):
    id: UUID
    patient_id: UUID
    related_patient_id: UUID
    related_patient_name: str
    # From the perspective of the patient whose page this is rendered on —
    # already flipped to the inverse label when this row was found via the
    # related_patient_id side. See service.list_relationships_for_patient.
    relationship_type: str
    notes: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
