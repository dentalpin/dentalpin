import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TreatmentConsumableCreate(BaseModel):
    treatment_id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity_needed: Decimal = Field(default=Decimal("1"), gt=0)


class TreatmentConsumableUpdate(BaseModel):
    quantity_needed: Decimal = Field(gt=0)


class TreatmentConsumableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clinic_id: uuid.UUID
    treatment_id: uuid.UUID
    inventory_item_id: uuid.UUID
    quantity_needed: Decimal
