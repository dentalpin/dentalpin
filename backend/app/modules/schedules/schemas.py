"""Pydantic schemas for the schedules module."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ShiftIn(BaseModel):
    """Incoming shift time range."""

    start_time: time
    end_time: time

    @model_validator(mode="after")
    def check_order(self) -> ShiftIn:
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


def _reject_overlaps(shifts: list[ShiftIn]) -> None:
    """Shifts of one day may touch (09–14, 14–18) but not overlap (#991)."""
    ordered = sorted(shifts, key=lambda s: s.start_time)
    for previous, current in zip(ordered, ordered[1:], strict=False):
        if current.start_time < previous.end_time:
            raise ValueError(
                f"shifts overlap: {previous.start_time:%H:%M}–{previous.end_time:%H:%M} "
                f"and {current.start_time:%H:%M}–{current.end_time:%H:%M}"
            )


class ShiftOut(ShiftIn):
    id: UUID

    model_config = ConfigDict(from_attributes=True)


class WeekdayShiftsIn(BaseModel):
    """Shifts for one weekday when updating a weekly schedule."""

    weekday: int = Field(ge=0, le=6)
    shifts: list[ShiftIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_overlaps(self) -> WeekdayShiftsIn:
        _reject_overlaps(self.shifts)
        return self


class WeekdayShiftsOut(BaseModel):
    weekday: int
    shifts: list[ShiftOut]


# --- Clinic weekly -----------------------------------------------------


class ClinicHoursResponse(BaseModel):
    """Full weekly view for a clinic. One row per weekday (0=Mon..6=Sun)."""

    id: UUID
    clinic_id: UUID
    timezone: str
    is_active: bool
    days: list[WeekdayShiftsOut]

    model_config = ConfigDict(from_attributes=True)


class ClinicHoursUpdate(BaseModel):
    """Full overwrite of the clinic's weekly shifts.

    Timezone is a core clinic metadata field managed via
    ``PUT /api/v1/auth/clinics`` — not accepted here so the schedules
    module never writes to core-owned data.
    """

    days: list[WeekdayShiftsIn]


# --- Clinic overrides -------------------------------------------------


class ClinicOverrideBase(BaseModel):
    start_date: date
    end_date: date
    kind: Literal["closed", "custom_hours"]
    reason: str | None = Field(default=None, max_length=200)
    shifts: list[ShiftIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dates_and_shifts(self) -> ClinicOverrideBase:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.kind == "closed" and self.shifts:
            raise ValueError("closed overrides must have no shifts")
        if self.kind == "custom_hours" and not self.shifts:
            raise ValueError("custom_hours overrides require at least one shift")
        _reject_overlaps(self.shifts)
        return self


class ClinicOverrideCreate(ClinicOverrideBase):
    pass


class ClinicOverrideUpdate(ClinicOverrideBase):
    pass


class ClinicOverrideResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    start_date: date
    end_date: date
    kind: str
    reason: str | None
    shifts: list[ShiftOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# --- Professional weekly ----------------------------------------------


class ProfessionalHoursResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    user_id: UUID
    is_active: bool
    days: list[WeekdayShiftsOut]

    model_config = ConfigDict(from_attributes=True)


class ProfessionalHoursUpdate(BaseModel):
    days: list[WeekdayShiftsIn]


# --- Professional overrides ------------------------------------------


class ProfessionalOverrideBase(BaseModel):
    start_date: date
    end_date: date
    kind: Literal["unavailable", "custom_hours"]
    reason: str | None = Field(default=None, max_length=200)
    shifts: list[ShiftIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dates_and_shifts(self) -> ProfessionalOverrideBase:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.kind == "unavailable" and self.shifts:
            raise ValueError("unavailable overrides must have no shifts")
        if self.kind == "custom_hours" and not self.shifts:
            raise ValueError("custom_hours overrides require at least one shift")
        _reject_overlaps(self.shifts)
        return self


class ProfessionalOverrideCreate(ProfessionalOverrideBase):
    pass


class ProfessionalOverrideUpdate(ProfessionalOverrideBase):
    pass


class ProfessionalOverrideResponse(BaseModel):
    id: UUID
    clinic_id: UUID
    user_id: UUID
    start_date: date
    end_date: date
    kind: str
    reason: str | None
    shifts: list[ShiftOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# --- Availability -----------------------------------------------------


AvailabilityState = Literal[
    "open",
    "clinic_closed",
    "professional_off",
]


class AvailabilityRange(BaseModel):
    start: datetime
    end: datetime
    state: AvailabilityState
    professional_id: UUID | None = None
    reason: str | None = None


class AvailabilityResponse(BaseModel):
    timezone: str
    ranges: list[AvailabilityRange]


# --- Analytics --------------------------------------------------------


class OccupancyRow(BaseModel):
    cabinet_id: UUID
    cabinet_name: str
    booked_minutes: int
    available_minutes: int
    occupancy_rate: float  # 0..1


class OccupancyResponse(BaseModel):
    start: date
    end: date
    rows: list[OccupancyRow]


class UtilizationRow(BaseModel):
    professional_id: UUID
    professional_name: str
    booked_minutes: int
    working_minutes: int
    utilization_rate: float


class UtilizationResponse(BaseModel):
    start: date
    end: date
    rows: list[UtilizationRow]


class PeakHourRow(BaseModel):
    hour: int = Field(ge=0, le=23)
    appointment_count: int


class PeakHoursResponse(BaseModel):
    start: date
    end: date
    rows: list[PeakHourRow]
