"""AppointmentService — business logic for scheduling.

Moved from ``app.modules.clinical.service`` in Fase B.2 chunk 1.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.auth.models import ClinicMembership
from app.core.events import EventType, event_bus
from app.modules.catalog.models import TreatmentCatalogItem  # noqa: F401
from app.modules.odontogram.models import Treatment
from app.modules.patients.models import Patient
from app.modules.treatment_plan.models import PlannedTreatmentItem

from .models import (
    Appointment,
    AppointmentCabinetEvent,
    AppointmentStatusEvent,
    AppointmentTreatment,
    Cabinet,
)
from .tz import as_utc, get_clinic_tz

# Canonical state machine. Mirrored in the frontend composable
# ``useAppointmentStatus.ts`` and kept in sync via a parity test
# (``tests/test_state_machine_parity.py``). Terminal states map to the
# empty set.
VALID_TRANSITIONS: dict[str, set[str]] = {
    "scheduled": {"confirmed", "checked_in", "cancelled", "no_show"},
    "confirmed": {"checked_in", "cancelled", "no_show"},
    "checked_in": {"in_treatment", "cancelled"},
    "in_treatment": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
    "no_show": set(),
}


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _plain_excerpt(text: str, limit: int = 200) -> str:
    """Strip HTML + collapse whitespace for event/timeline payload excerpts."""
    stripped = _HTML_TAG_RE.sub(" ", text or "")
    collapsed = _WS_RE.sub(" ", stripped).strip()
    return collapsed[:limit]


class InvalidTransitionError(ValueError):
    """Raised when a requested status transition is not allowed."""


class AlreadyInStateError(ValueError):
    """Raised when a transition targets the appointment's current state."""


class CabinetRequiredError(ValueError):
    """Raised when moving to ``in_treatment`` without a cabinet assigned."""


class CabinetService:
    """CRUD for clinic cabinets."""

    @staticmethod
    async def list_cabinets(db: AsyncSession, clinic_id: UUID) -> list[Cabinet]:
        result = await db.execute(
            select(Cabinet)
            .where(Cabinet.clinic_id == clinic_id)
            .order_by(Cabinet.display_order, Cabinet.name)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_cabinet(db: AsyncSession, clinic_id: UUID, cabinet_id: UUID) -> Cabinet | None:
        result = await db.execute(
            select(Cabinet).where(Cabinet.id == cabinet_id, Cabinet.clinic_id == clinic_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_name(db: AsyncSession, clinic_id: UUID, name: str) -> Cabinet | None:
        result = await db.execute(
            select(Cabinet).where(Cabinet.clinic_id == clinic_id, Cabinet.name == name)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_cabinet(db: AsyncSession, clinic_id: UUID, data: dict) -> Cabinet:
        if data.get("display_order") is None:
            # Append at the end.
            max_order = (
                await db.execute(
                    select(func.coalesce(func.max(Cabinet.display_order), -1)).where(
                        Cabinet.clinic_id == clinic_id
                    )
                )
            ).scalar_one()
            data["display_order"] = int(max_order) + 1
        if data.get("is_active") is None:
            data["is_active"] = True

        cabinet = Cabinet(clinic_id=clinic_id, **data)
        db.add(cabinet)
        await db.flush()
        await db.refresh(cabinet)
        return cabinet

    @staticmethod
    async def update_cabinet(db: AsyncSession, cabinet: Cabinet, data: dict) -> Cabinet:
        old_name = cabinet.name
        for key, value in data.items():
            if value is not None:
                setattr(cabinet, key, value)
        await db.flush()

        # Keep the denormalized appointments.cabinet string in sync.
        if "name" in data and data["name"] != old_name:
            from sqlalchemy import update as sql_update

            await db.execute(
                sql_update(Appointment)
                .where(
                    Appointment.clinic_id == cabinet.clinic_id,
                    Appointment.cabinet_id == cabinet.id,
                )
                .values(cabinet=cabinet.name)
            )

        return cabinet

    @staticmethod
    async def delete_cabinet(db: AsyncSession, cabinet: Cabinet) -> None:
        await db.delete(cabinet)
        await db.flush()


class AppointmentService:
    """Service for appointment operations."""

    @staticmethod
    async def list_appointments(
        db: AsyncSession,
        clinic_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cabinet: str | None = None,
        professional_id: UUID | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 100,
        *,
        patient_id: UUID | None = None,
        order: str = "asc",
    ) -> tuple[list[Appointment], int]:
        """List appointments with filters.

        Naive ``start_date``/``end_date`` are clinic-local (issue #161).
        ``order`` sorts by ``start_time`` (``asc`` default, ``desc`` for
        most-recent-first consumers).
        """
        if (start_date and start_date.tzinfo is None) or (end_date and end_date.tzinfo is None):
            tz = await get_clinic_tz(db, clinic_id)
            if start_date and start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=tz)
            if end_date and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=tz)

        page_size = min(max(page_size, 1), 500)
        page = max(page, 1)
        offset = (page - 1) * page_size

        query = (
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.professional),
                selectinload(Appointment.treatments).options(
                    selectinload(AppointmentTreatment.planned_item).options(
                        selectinload(PlannedTreatmentItem.treatment).options(
                            selectinload(Treatment.teeth),
                            selectinload(Treatment.catalog_item),
                        ),
                        selectinload(PlannedTreatmentItem.treatment_plan),
                    ),
                    selectinload(AppointmentTreatment.catalog_item),
                ),
            )
            .where(Appointment.clinic_id == clinic_id)
        )

        if start_date:
            query = query.where(Appointment.start_time >= start_date)
        if end_date:
            query = query.where(Appointment.start_time <= end_date)
        if cabinet:
            query = query.where(Appointment.cabinet == cabinet)
        if professional_id:
            query = query.where(Appointment.professional_id == professional_id)
        if patient_id:
            query = query.where(Appointment.patient_id == patient_id)
        if status:
            query = query.where(Appointment.status == status)

        count_filters = [Appointment.clinic_id == clinic_id]
        if start_date:
            count_filters.append(Appointment.start_time >= start_date)
        if end_date:
            count_filters.append(Appointment.start_time <= end_date)
        if cabinet:
            count_filters.append(Appointment.cabinet == cabinet)
        if professional_id:
            count_filters.append(Appointment.professional_id == professional_id)
        if patient_id:
            count_filters.append(Appointment.patient_id == patient_id)
        if status:
            count_filters.append(Appointment.status == status)
        total = (
            await db.execute(select(func.count(Appointment.id)).where(*count_filters))
        ).scalar() or 0

        query = query.order_by(
            Appointment.start_time.desc() if order == "desc" else Appointment.start_time
        )
        query = query.offset(offset).limit(page_size)
        result = await db.execute(query)
        return list(result.scalars().all()), total

    @staticmethod
    async def list_status_events(
        db: AsyncSession, clinic_id: UUID, appointment_id: UUID
    ) -> list[AppointmentStatusEvent]:
        """Return the full audit trail for an appointment in chronological
        order. ``clinic_id`` is enforced here so the history endpoint stays
        multi-tenant safe.
        """
        result = await db.execute(
            select(AppointmentStatusEvent)
            .options(selectinload(AppointmentStatusEvent.actor))
            .where(
                AppointmentStatusEvent.appointment_id == appointment_id,
                AppointmentStatusEvent.clinic_id == clinic_id,
            )
            .order_by(AppointmentStatusEvent.changed_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def list_cabinet_events(
        db: AsyncSession, clinic_id: UUID, appointment_id: UUID
    ) -> list[AppointmentCabinetEvent]:
        """Return the cabinet assignment history for an appointment
        (chronological, multi-tenant-safe)."""
        result = await db.execute(
            select(AppointmentCabinetEvent)
            .options(
                selectinload(AppointmentCabinetEvent.actor),
                selectinload(AppointmentCabinetEvent.from_cabinet),
                selectinload(AppointmentCabinetEvent.to_cabinet),
            )
            .where(
                AppointmentCabinetEvent.appointment_id == appointment_id,
                AppointmentCabinetEvent.clinic_id == clinic_id,
            )
            .order_by(AppointmentCabinetEvent.changed_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def get_appointment(
        db: AsyncSession, clinic_id: UUID, appointment_id: UUID
    ) -> Appointment | None:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.patient),
                selectinload(Appointment.professional),
                selectinload(Appointment.treatments).options(
                    selectinload(AppointmentTreatment.planned_item).options(
                        selectinload(PlannedTreatmentItem.treatment).options(
                            selectinload(Treatment.teeth),
                            selectinload(Treatment.catalog_item),
                        ),
                        selectinload(PlannedTreatmentItem.treatment_plan),
                    ),
                    selectinload(AppointmentTreatment.catalog_item),
                ),
            )
            .where(
                Appointment.id == appointment_id,
                Appointment.clinic_id == clinic_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_patient_access(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> bool:
        result = await db.execute(
            select(Patient.id).where(
                Patient.id == patient_id,
                Patient.clinic_id == clinic_id,
                Patient.status != "archived",
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def validate_professional_access(
        db: AsyncSession, clinic_id: UUID, professional_id: UUID
    ) -> bool:
        result = await db.execute(
            select(ClinicMembership.id).where(
                ClinicMembership.user_id == professional_id,
                ClinicMembership.clinic_id == clinic_id,
                ClinicMembership.is_professional.is_(True),
            )
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def validate_planned_items(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        planned_item_ids: list[UUID],
    ) -> None:
        """Validate planned treatment items for appointment.

        Raises ValueError with details if validation fails.
        """
        if not planned_item_ids:
            return

        result = await db.execute(
            select(PlannedTreatmentItem)
            .options(selectinload(PlannedTreatmentItem.treatment_plan))
            .where(PlannedTreatmentItem.id.in_(planned_item_ids))
        )
        items = {item.id: item for item in result.scalars().all()}

        errors = []
        for item_id in planned_item_ids:
            item = items.get(item_id)
            if not item:
                errors.append(f"Treatment item {item_id} not found")
                continue
            if item.clinic_id != clinic_id:
                errors.append(f"Treatment item {item_id} not found")
                continue
            plan = item.treatment_plan
            if not plan or plan.patient_id != patient_id:
                errors.append(f"Treatment item {item_id} does not belong to patient")
                continue
            # `pending` (plan confirmed, budget not yet accepted) is bookable
            # on purpose: an unconfirmed `draft` already is, so confirming a
            # plan must not take that away — clinics book the first visit while
            # the patient is still deciding (#108). Terminal states stay out.
            if plan.status not in ("active", "draft", "pending"):
                errors.append(f"Treatment item {item_id} belongs to {plan.status} plan")
                continue
            if item.status != "pending":
                errors.append(f"Treatment item {item_id} is already {item.status}")

        if errors:
            raise ValueError("; ".join(errors))

    @staticmethod
    async def _resolve_cabinet(db: AsyncSession, clinic_id: UUID, data: dict) -> None:
        """Ensure ``data`` ends up with matching ``cabinet_id`` + ``cabinet``.

        Accepts either ``cabinet_id`` or the ``cabinet`` name; if neither
        is provided, leaves both as ``None`` — cabinet assignment is now
        deferred-by-design (issue #51). Raises ``ValueError`` only when a
        non-null reference can't be resolved.
        """
        cabinet_id = data.get("cabinet_id")
        cabinet_name = data.get("cabinet")

        cab: Cabinet | None = None
        if cabinet_id:
            cab = await CabinetService.get_cabinet(db, clinic_id, cabinet_id)
            if cab is None:
                raise ValueError(f"Cabinet not found: {cabinet_id}")
        elif cabinet_name:
            cab = await CabinetService.get_by_name(db, clinic_id, cabinet_name)
            if cab is None:
                raise ValueError(f"Cabinet not found: {cabinet_name}")

        if cab is not None:
            data["cabinet_id"] = cab.id
            data["cabinet"] = cab.name
        else:
            # Deferred assignment — the appointment exists without a chair.
            data["cabinet_id"] = None
            data["cabinet"] = None

    @staticmethod
    async def _normalize_times(db: AsyncSession, clinic_id: UUID, data: dict) -> None:
        """Normalize ``start_time``/``end_time`` in ``data`` to UTC instants.

        Naive values are interpreted as clinic-local wall-clock (issue
        #161); aware values keep their instant. No-op when neither field
        is present (e.g. partial updates).
        """
        keys = [k for k in ("start_time", "end_time") if isinstance(data.get(k), datetime)]
        if not keys:
            return
        tz = await get_clinic_tz(db, clinic_id)
        for key in keys:
            data[key] = as_utc(data[key], tz)

    @staticmethod
    async def create_appointment(
        db: AsyncSession,
        clinic_id: UUID,
        data: dict,
        created_by: UUID | None = None,
    ) -> Appointment:
        """Create an appointment. Raises IntegrityError on slot conflict.

        Records the synthetic initial status event (``from_status=None``,
        ``to_status=<status>``) so downstream analytics can always count on
        the history being complete from first principles.
        """
        planned_item_ids = data.pop("planned_item_ids", None)

        await AppointmentService._normalize_times(db, clinic_id, data)

        await AppointmentService._resolve_cabinet(db, clinic_id, data)

        if planned_item_ids and data.get("patient_id"):
            await AppointmentService.validate_planned_items(
                db, clinic_id, data["patient_id"], planned_item_ids
            )

        now = datetime.now(UTC)
        data.setdefault("current_status_since", now)

        # If the caller pre-assigned a cabinet (the happy path when the
        # chair is known up-front), stamp the denormalized audit columns so
        # the UI doesn't need to join the event table.
        if data.get("cabinet_id") is not None:
            data.setdefault("cabinet_assigned_at", now)
            data.setdefault("cabinet_assigned_by", created_by)

        appointment = Appointment(clinic_id=clinic_id, **data)
        db.add(appointment)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise

        db.add(
            AppointmentStatusEvent(
                clinic_id=clinic_id,
                appointment_id=appointment.id,
                from_status=None,
                to_status=appointment.status,
                changed_at=appointment.current_status_since,
                changed_by=created_by,
            )
        )

        # Seed the cabinet audit trail for pre-assigned appointments —
        # deferred ones get their first event when the receptionist drops
        # the card on a cabinet in the kanban.
        if appointment.cabinet_id is not None:
            db.add(
                AppointmentCabinetEvent(
                    clinic_id=clinic_id,
                    appointment_id=appointment.id,
                    from_cabinet_id=None,
                    to_cabinet_id=appointment.cabinet_id,
                    changed_at=now,
                    changed_by=created_by,
                )
            )

        if planned_item_ids:
            for order, planned_item_id in enumerate(planned_item_ids):
                planned_item = await db.get(PlannedTreatmentItem, planned_item_id)
                catalog_item_id = None
                if planned_item:
                    await db.refresh(planned_item, ["treatment"])
                    if planned_item.treatment:
                        catalog_item_id = planned_item.treatment.catalog_item_id

                treatment = AppointmentTreatment(
                    appointment_id=appointment.id,
                    planned_treatment_item_id=planned_item_id,
                    catalog_item_id=catalog_item_id,
                    display_order=order,
                )
                db.add(treatment)
            await db.flush()

        await event_bus.publish(
            EventType.APPOINTMENT_SCHEDULED,
            {
                "appointment_id": str(appointment.id),
                "clinic_id": str(appointment.clinic_id),
                "patient_id": str(appointment.patient_id) if appointment.patient_id else None,
                "professional_id": str(appointment.professional_id),
                "start_time": appointment.start_time.isoformat(),
                "end_time": appointment.end_time.isoformat(),
                "treatment_type": appointment.treatment_type,
                "cabinet": appointment.cabinet,
            },
            db=db,
        )

        await db.refresh(appointment, ["patient", "professional", "treatments"])
        for treatment in appointment.treatments:
            await db.refresh(treatment, ["planned_item", "catalog_item"])
            if treatment.planned_item:
                await db.refresh(treatment.planned_item, ["treatment", "treatment_plan"])
                if treatment.planned_item.treatment:
                    await db.refresh(treatment.planned_item.treatment, ["teeth", "catalog_item"])

        return appointment

    @staticmethod
    async def update_appointment(
        db: AsyncSession,
        appointment: Appointment,
        data: dict,
        changed_by: UUID | None = None,
    ) -> Appointment:
        """Update an appointment.

        When ``data`` carries a ``status`` field, the status change is funneled
        through :meth:`transition` so the audit trail, ``current_status_since``
        and the bus events stay consistent with every other path that mutates
        status.
        """
        requested_status = data.pop("status", None)

        planned_item_ids = data.pop("planned_item_ids", None)

        await AppointmentService._normalize_times(db, appointment.clinic_id, data)

        # Cabinet changes go through assign_cabinet() so the audit trail
        # + bus event fire. Pop the fields here and apply after the core
        # update has flushed. A null explicit in data means "unassign" —
        # the service distinguishes that from "field not present" via
        # sentinel below.
        _cabinet_unset = object()
        requested_cabinet_id = data.pop("cabinet_id", _cabinet_unset)
        requested_cabinet_name = data.pop("cabinet", _cabinet_unset)
        cabinet_change_requested = not (
            requested_cabinet_id is _cabinet_unset and requested_cabinet_name is _cabinet_unset
        )
        resolved_cabinet_id: UUID | None = None
        if cabinet_change_requested:
            tmp: dict = {
                "cabinet_id": (
                    None if requested_cabinet_id is _cabinet_unset else requested_cabinet_id
                ),
                "cabinet": (
                    None if requested_cabinet_name is _cabinet_unset else requested_cabinet_name
                ),
            }
            await AppointmentService._resolve_cabinet(db, appointment.clinic_id, tmp)
            resolved_cabinet_id = tmp["cabinet_id"]

        if planned_item_ids:
            patient_id = data.get("patient_id") or appointment.patient_id
            if patient_id:
                await AppointmentService.validate_planned_items(
                    db, appointment.clinic_id, patient_id, planned_item_ids
                )

        for key, value in data.items():
            if value is not None:
                setattr(appointment, key, value)

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise

        if planned_item_ids is not None:
            for existing in list(appointment.treatments):
                await db.delete(existing)
            await db.flush()

            for order, planned_item_id in enumerate(planned_item_ids):
                planned_item = await db.get(PlannedTreatmentItem, planned_item_id)
                catalog_item_id = None
                if planned_item:
                    await db.refresh(planned_item, ["treatment"])
                    if planned_item.treatment:
                        catalog_item_id = planned_item.treatment.catalog_item_id

                treatment = AppointmentTreatment(
                    appointment_id=appointment.id,
                    planned_treatment_item_id=planned_item_id,
                    catalog_item_id=catalog_item_id,
                    display_order=order,
                )
                db.add(treatment)
            await db.flush()

            await db.refresh(appointment, ["treatments"])
            for treatment in appointment.treatments:
                await db.refresh(treatment, ["planned_item", "catalog_item"])
                if treatment.planned_item:
                    await db.refresh(treatment.planned_item, ["treatment", "treatment_plan"])
                    if treatment.planned_item.treatment:
                        await db.refresh(
                            treatment.planned_item.treatment, ["teeth", "catalog_item"]
                        )

        if cabinet_change_requested and resolved_cabinet_id != appointment.cabinet_id:
            await AppointmentService.assign_cabinet(
                db, appointment, resolved_cabinet_id, changed_by=changed_by
            )

        if requested_status is not None and requested_status != appointment.status:
            await AppointmentService.transition(
                db, appointment, requested_status, changed_by=changed_by
            )
        else:
            await event_bus.publish(
                EventType.APPOINTMENT_UPDATED,
                {
                    "appointment_id": str(appointment.id),
                    "clinic_id": str(appointment.clinic_id),
                    "patient_id": (str(appointment.patient_id) if appointment.patient_id else None),
                },
            )

        return appointment

    @staticmethod
    async def cancel_appointment(
        db: AsyncSession,
        appointment: Appointment,
        changed_by: UUID | None = None,
    ) -> Appointment:
        """Cancel an appointment (delegates to :meth:`transition`)."""
        if appointment.status == "cancelled":
            return appointment
        try:
            return await AppointmentService.transition(
                db, appointment, "cancelled", changed_by=changed_by
            )
        except InvalidTransitionError:
            # Terminal states (completed / no_show) are not cancellable by
            # contract — surface a 400 at the router layer.
            raise

    @staticmethod
    async def transition(
        db: AsyncSession,
        appointment: Appointment,
        to_status: str,
        changed_by: UUID | None = None,
        note: str | None = None,
    ) -> Appointment:
        """Transition an appointment to ``to_status``.

        - Validates against :data:`VALID_TRANSITIONS`.
        - Appends a row to ``appointment_status_events``.
        - Updates ``appointment.status`` and ``current_status_since``.
        - Publishes the specific bus event (completed / cancelled / no_show)
          so existing subscribers keep working. The generic
          ``APPOINTMENT_STATUS_CHANGED`` event is wired in chunk 2.

        Raises :class:`AlreadyInStateError` if ``to_status`` equals the
        current status, and :class:`InvalidTransitionError` otherwise.
        """
        from_status = appointment.status

        if to_status == from_status:
            raise AlreadyInStateError(f"Appointment is already in status '{to_status}'")
        allowed = VALID_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(f"Cannot transition from '{from_status}' to '{to_status}'")

        # Operational rule: a patient can't be "in treatment" without a
        # chair. The kanban UI forces the user to drop the card on a
        # specific cabinet box — if they somehow call the API directly
        # without one, fail loudly with a dedicated exception so the
        # frontend toast reads "Assign a cabinet first".
        if to_status == "in_treatment" and appointment.cabinet_id is None:
            raise CabinetRequiredError("A cabinet must be assigned before moving to 'in_treatment'")

        now = datetime.now(UTC)
        event = AppointmentStatusEvent(
            clinic_id=appointment.clinic_id,
            appointment_id=appointment.id,
            from_status=from_status,
            to_status=to_status,
            changed_at=now,
            changed_by=changed_by,
            note=note,
        )
        db.add(event)

        appointment.status = to_status
        appointment.current_status_since = now
        await db.flush()

        payload = {
            "appointment_id": str(appointment.id),
            "clinic_id": str(appointment.clinic_id),
            "patient_id": (str(appointment.patient_id) if appointment.patient_id else None),
            "professional_id": str(appointment.professional_id),
            "treatment_type": appointment.treatment_type,
            "cabinet": appointment.cabinet,
            "start_time": appointment.start_time.isoformat(),
            "end_time": appointment.end_time.isoformat(),
            "from_status": from_status,
            "to_status": to_status,
            "changed_at": now.isoformat(),
            "changed_by": str(changed_by) if changed_by else None,
            "note": note,
        }

        # Always publish the generic transition event — the recommended
        # subscription for new consumers.
        await event_bus.publish(EventType.APPOINTMENT_STATUS_CHANGED, payload)

        # Specific events are kept for backward compatibility with existing
        # subscribers (patient_timeline, billing hooks, etc.).
        specific = {
            "confirmed": EventType.APPOINTMENT_CONFIRMED,
            "checked_in": EventType.APPOINTMENT_CHECKED_IN,
            "in_treatment": EventType.APPOINTMENT_IN_TREATMENT,
            "completed": EventType.APPOINTMENT_COMPLETED,
            "cancelled": EventType.APPOINTMENT_CANCELLED,
            "no_show": EventType.APPOINTMENT_NO_SHOW,
        }.get(to_status)
        if specific is not None:
            await event_bus.publish(specific, payload, db=db)

        return appointment

    @staticmethod
    async def assign_cabinet(
        db: AsyncSession,
        appointment: Appointment,
        cabinet_id: UUID | None,
        changed_by: UUID | None = None,
        note: str | None = None,
    ) -> Appointment:
        """Assign, reassign, or unassign (``cabinet_id=None``) a cabinet.

        - Resolves the target cabinet (validates it exists and belongs to
          the clinic). Detects slot conflicts with other non-cancelled
          appointments and raises ``IntegrityError`` via DB constraint.
        - Inserts an ``AppointmentCabinetEvent`` row.
        - Updates the denormalized audit columns on ``Appointment``.
        - Publishes ``APPOINTMENT_CABINET_CHANGED`` on the bus.

        Early-returns without touching anything if the target equals the
        current cabinet — a no-op from the operational perspective.
        """
        from_cabinet_id = appointment.cabinet_id
        if cabinet_id == from_cabinet_id:
            return appointment

        target_cabinet: Cabinet | None = None
        if cabinet_id is not None:
            target_cabinet = await CabinetService.get_cabinet(db, appointment.clinic_id, cabinet_id)
            if target_cabinet is None:
                raise ValueError(f"Cabinet not found: {cabinet_id}")

        now = datetime.now(UTC)
        db.add(
            AppointmentCabinetEvent(
                clinic_id=appointment.clinic_id,
                appointment_id=appointment.id,
                from_cabinet_id=from_cabinet_id,
                to_cabinet_id=cabinet_id,
                changed_at=now,
                changed_by=changed_by,
                note=note,
            )
        )

        appointment.cabinet_id = cabinet_id
        appointment.cabinet = target_cabinet.name if target_cabinet else None
        appointment.cabinet_assigned_at = now if cabinet_id is not None else None
        appointment.cabinet_assigned_by = changed_by if cabinet_id is not None else None

        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            raise

        await event_bus.publish(
            EventType.APPOINTMENT_CABINET_CHANGED,
            {
                "appointment_id": str(appointment.id),
                "clinic_id": str(appointment.clinic_id),
                "patient_id": (str(appointment.patient_id) if appointment.patient_id else None),
                "professional_id": str(appointment.professional_id),
                "from_cabinet_id": (str(from_cabinet_id) if from_cabinet_id else None),
                "to_cabinet_id": str(cabinet_id) if cabinet_id else None,
                "changed_at": now.isoformat(),
                "changed_by": str(changed_by) if changed_by else None,
                "note": note,
            },
        )

        return appointment

    # ------------------------------------------------------------------
    # Visit-level clinical note (AppointmentTreatment.notes)
    # ------------------------------------------------------------------

    @staticmethod
    async def update_appointment_treatment_note(
        db: AsyncSession,
        clinic_id: UUID,
        appointment_treatment_id: UUID,
        user_id: UUID,
        *,
        notes: str | None = None,
        completed_in_appointment: bool | None = None,
    ) -> AppointmentTreatment | None:
        """Update visit-level clinical note on an AppointmentTreatment.

        Publishes ``AGENDA_VISIT_NOTE_UPDATED`` so ``patient_timeline`` and
        other subscribers can record the change without importing agenda.
        """
        result = await db.execute(
            select(AppointmentTreatment, Appointment)
            .join(Appointment, AppointmentTreatment.appointment_id == Appointment.id)
            .where(
                AppointmentTreatment.id == appointment_treatment_id,
                Appointment.clinic_id == clinic_id,
            )
        )
        row = result.first()
        if row is None:
            return None
        apt_treatment, appointment = row

        changed = False
        if notes is not None:
            apt_treatment.notes = notes
            changed = True
        if completed_in_appointment is not None:
            apt_treatment.completed_in_appointment = completed_in_appointment
            changed = True
        if not changed:
            return apt_treatment

        await db.flush()

        if notes is not None:
            excerpt = _plain_excerpt(notes)
            await event_bus.publish(
                EventType.AGENDA_VISIT_NOTE_UPDATED,
                {
                    "clinic_id": str(clinic_id),
                    "patient_id": str(appointment.patient_id) if appointment.patient_id else None,
                    "appointment_id": str(appointment.id),
                    "appointment_treatment_id": str(apt_treatment.id),
                    "plan_item_id": str(apt_treatment.planned_treatment_item_id)
                    if apt_treatment.planned_treatment_item_id
                    else None,
                    "user_id": str(user_id),
                    "body_excerpt": excerpt,
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )

        return apt_treatment
