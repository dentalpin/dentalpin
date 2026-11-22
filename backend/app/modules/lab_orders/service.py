"""Business logic for lab work orders."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi import status as http_status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_bus
from app.core.events.types import EventType
from app.core.utils.dates import clinic_today_for
from app.modules.contacts.models import Contact
from app.modules.patients.models import Patient

from .models import LabOrder
from .schemas import LabOrderCreate, LabOrderUpdate


def _response_dict(order: LabOrder, patient_name: str, lab_name: str) -> dict:
    return {
        "id": order.id,
        "clinic_id": order.clinic_id,
        "patient_id": order.patient_id,
        "patient_name": patient_name,
        "lab_contact_id": order.lab_contact_id,
        "lab_contact_name": lab_name,
        "work_type": order.work_type,
        "tooth_reference": order.tooth_reference,
        "impression_type": order.impression_type,
        "antagonist_info": order.antagonist_info,
        "shade": order.shade,
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
    async def _assert_patient(db: AsyncSession, clinic_id: UUID, patient_id: UUID) -> None:
        stmt = select(Patient.id).where(Patient.id == patient_id, Patient.clinic_id == clinic_id)
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "patient_id does not match a patient in this clinic",
            )

    @staticmethod
    async def _assert_contact(db: AsyncSession, clinic_id: UUID, contact_id: UUID) -> None:
        # Only a lab contact: the form lists ``contact_type='lab'`` only, but
        # the API and the copilot tool took a supplier or delegate too (#985).
        stmt = select(Contact.id).where(
            Contact.id == contact_id,
            Contact.clinic_id == clinic_id,
            Contact.contact_type == "lab",
        )
        if (await db.execute(stmt)).scalar_one_or_none() is None:
            raise HTTPException(
                http_status.HTTP_400_BAD_REQUEST,
                "lab_contact_id does not match a lab contact in this clinic",
            )

    @staticmethod
    async def _enrich(db: AsyncSession, clinic_id: UUID, orders: list[LabOrder]) -> list[dict]:
        if not orders:
            return []
        patient_ids = {order.patient_id for order in orders}
        contact_ids = {order.lab_contact_id for order in orders}
        patients = (
            (
                await db.execute(
                    select(Patient).where(
                        Patient.id.in_(patient_ids), Patient.clinic_id == clinic_id
                    )
                )
            )
            .scalars()
            .all()
        )
        contacts = (
            (
                await db.execute(
                    select(Contact).where(
                        Contact.id.in_(contact_ids), Contact.clinic_id == clinic_id
                    )
                )
            )
            .scalars()
            .all()
        )
        patient_names = {patient.id: patient.full_name for patient in patients}
        contact_names = {contact.id: contact.name for contact in contacts}
        return [
            _response_dict(
                order,
                patient_names.get(order.patient_id, "—"),
                contact_names.get(order.lab_contact_id, "—"),
            )
            for order in orders
        ]

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
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        rows = (
            (
                await db.execute(
                    stmt.order_by(LabOrder.sent_date.desc(), LabOrder.id)
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            )
            .scalars()
            .all()
        )
        return list(rows), total

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
        return await LabOrderService._enrich(db, clinic_id, orders), total

    @staticmethod
    async def get_order(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> LabOrder:
        stmt = select(LabOrder).where(LabOrder.id == order_id, LabOrder.clinic_id == clinic_id)
        order = (await db.execute(stmt)).scalar_one_or_none()
        if order is None:
            raise HTTPException(http_status.HTTP_404_NOT_FOUND, "Lab order not found")
        return order

    @staticmethod
    async def get_order_response(db: AsyncSession, clinic_id: UUID, order_id: UUID) -> dict:
        order = await LabOrderService.get_order(db, clinic_id, order_id)
        return (await LabOrderService._enrich(db, clinic_id, [order]))[0]

    @staticmethod
    async def create_order(
        db: AsyncSession, clinic_id: UUID, payload: LabOrderCreate, created_by: UUID | None
    ) -> LabOrder:
        await LabOrderService._assert_patient(db, clinic_id, payload.patient_id)
        await LabOrderService._assert_contact(db, clinic_id, payload.lab_contact_id)
        order = LabOrder(
            clinic_id=clinic_id, created_by=created_by, status="sent", **payload.model_dump()
        )
        db.add(order)
        await db.commit()
        await db.refresh(order)
        return order

    @staticmethod
    async def update_order(
        db: AsyncSession, clinic_id: UUID, order_id: UUID, payload: LabOrderUpdate
    ) -> LabOrder:
        order = await LabOrderService.get_order(db, clinic_id, order_id)
        if payload.lab_contact_id is not None:
            await LabOrderService._assert_contact(db, clinic_id, payload.lab_contact_id)
        old_status = order.status
        data = payload.model_dump(exclude_unset=True)
        # Stamp only on the transition *into* received — a repeated PATCH
        # with status=received must not overwrite the original receipt date.
        if (
            data.get("status") == "received"
            and "received_date" not in data
            and old_status != "received"
        ):
            data["received_date"] = await clinic_today_for(db, clinic_id)
        for field, value in data.items():
            setattr(order, field, value)
        await db.flush()
        # ADR 0019 — publish *inside* the transaction with the publisher's
        # session so transactional subscribers see the updated row and roll
        # back with it; the caller (router / agent runtime) owns the commit.
        if old_status != order.status:
            await event_bus.publish(
                EventType.LAB_ORDER_STATUS_CHANGED,
                {
                    "clinic_id": str(clinic_id),
                    "order_id": str(order.id),
                    "patient_id": str(order.patient_id),
                    "status": order.status,
                    "work_type": order.work_type,
                    "tooth_reference": order.tooth_reference,
                },
                db=db,
            )
        await db.commit()
        await db.refresh(order)
        return order
