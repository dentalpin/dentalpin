"""LabOrderService — business logic for lab work order CRUD and status tracking."""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus

# Synchronous cross-module reads of `patients` and `contacts` — allowed
# because both are listed in this module's manifest.depends (ADR 0002 / 0003).
from app.modules.contacts.models import Contact
from app.modules.patients.models import Patient

from .models import LabOrder
from .schemas import LabOrderCreate, LabOrderUpdate


def _to_response_dict(order: LabOrder, patient_name: str, lab_contact_name: str) -> dict:
    return {
        "id": order.id,
        "clinic_id": order.clinic_id,
        "patient_id": order.patient_id,
        "patient_name": patient_name,
        "lab_contact_id": order.lab_contact_id,
        "lab_contact_name": lab_contact_name,
        "work_type": order.work_type,
        "tooth_reference": order.tooth_reference,
        "status": order.status,
        "sent_date": order.sent_date,
        "expected_date": order.expected_date,
        "received_date": order.received_date,
        "notes": order.notes,
        "created_by": order.created_by,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
    }


class LabOrderService:
    @staticmethod
    async def _assert_contact_exists(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> None:
        stmt = select(Contact.id).where(Contact.id == contact_id, Contact.clinic_id == clinic_id)
        found = (await db.execute(stmt)).scalar_one_or_none()
        if found is None:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="lab_contact_id does not match a contact in this clinic",
            )

    @staticmethod
    async def _enrich(db: AsyncSession, orders: list[LabOrder]) -> list[dict]:
        """Batch-fetch patient and contact names for a page of orders."""
        if not orders:
            return []

        patient_ids = {o.patient_id for o in orders}
        contact_ids = {o.lab_contact_id for o in orders}

        patients = (
            (await db.execute(select(Patient).where(Patient.id.in_(patient_ids))))
            .scalars()
            .all()
        )
        contacts = (
            (await db.execute(select(Contact).where(Contact.id.in_(contact_ids))))
            .scalars()
            .all()
        )
        patient_names = {p.id: p.full_name for p in patients}
        contact_names = {c.id: c.name for c in contacts}

        return [
            _to_response_dict(
                o,
                patient_names.get(o.patient_id, "—"),
                contact_names.get(o.lab_contact_id, "—"),
            )
            for o in orders
        ]

    @staticmethod
    async def list_order_responses(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID | None = None,
        lab_contact_id: UUID | None = None,
        order_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[dict], int]:
        orders, total = await LabOrderService.list_orders(
            db, clinic_id, patient_id, lab_contact_id, order_status, page, page_size
        )
        return await LabOrderService._enrich(db, orders), total

    @staticmethod
    async def get_order_response(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> dict:
        order = await LabOrderService.get_order(db, clinic_id, order_id)
        enriched = await LabOrderService._enrich(db, [order])
        return enriched[0]

    @staticmethod
    async def create_order(
        db: AsyncSession, clinic_id: UUID, payload: LabOrderCreate, created_by: UUID | None
    ) -> LabOrder:
        await LabOrderService._assert_contact_exists(db, clinic_id, payload.lab_contact_id)
        order = LabOrder(
            clinic_id=clinic_id,
            patient_id=payload.patient_id,
            lab_contact_id=payload.lab_contact_id,
            work_type=payload.work_type,
            tooth_reference=payload.tooth_reference,
            sent_date=payload.sent_date,
            expected_date=payload.expected_date,
            notes=payload.notes,
            status="sent",
            created_by=created_by,
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def list_orders(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID | None = None,
        lab_contact_id: UUID | None = None,
        order_status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[LabOrder], int]:
        stmt = select(LabOrder).where(LabOrder.clinic_id == clinic_id)
        if patient_id:
            stmt = stmt.where(LabOrder.patient_id == patient_id)
        if lab_contact_id:
            stmt = stmt.where(LabOrder.lab_contact_id == lab_contact_id)
        if order_status:
            stmt = stmt.where(LabOrder.status == order_status)

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            stmt.order_by(LabOrder.sent_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows), total

    @staticmethod
    async def get_order(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> LabOrder:
        stmt = select(LabOrder).where(LabOrder.id == order_id, LabOrder.clinic_id == clinic_id)
        order = (await db.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND, detail="Lab order not found"
            )
        return order

    @staticmethod
    async def update_order(
        db: AsyncSession, clinic_id: UUID, order_id: UUID, payload: LabOrderUpdate
    ) -> LabOrder:
        order = await LabOrderService.get_order(db, clinic_id, order_id)
        if payload.lab_contact_id is not None:
            await LabOrderService._assert_contact_exists(db, clinic_id, payload.lab_contact_id)

        old_status = order.status
        data = payload.model_dump(exclude_unset=True)
        # Convenience: marking an order "received" auto-stamps today's date
        # if the caller didn't supply one explicitly.
        if data.get("status") == "received" and "received_date" not in data:
            data["received_date"] = date.today()

        for field, value in data.items():
            setattr(order, field, value)
        await db.commit()
        await db.refresh(order)

        # Phase 6: lets the `tasks` module auto-create a handoff task when
        # an order becomes "ready", without lab_orders needing to know
        # tasks exists — tasks subscribes to this, lab_orders just announces
        # it. Plain string event, not in the core EventType enum, since
        # this is a custom-module connector, not a core event.
        # Guard on old_status != order.status (not just "status" in data) so
        # a repeated/duplicate request with the same status can never
        # publish twice and create duplicate tasks.
        if "status" in data and order.status != old_status:
            await event_bus.publish(
                "lab_order.status_changed",
                {
                    "clinic_id": str(clinic_id),
                    "order_id": str(order.id),
                    "patient_id": str(order.patient_id),
                    "status": order.status,
                    "work_type": order.work_type,
                    "tooth_reference": order.tooth_reference,
                },
            )

        return order

    @staticmethod
    async def delete_order(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> None:
        order = await LabOrderService.get_order(db, clinic_id, order_id)
        await db.delete(order)
        await db.commit()
