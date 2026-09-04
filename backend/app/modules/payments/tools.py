"""Agent tools for the payments module.

Thin wrappers over ``PaymentReportsService`` — no business logic here.
Clinic-scoped; RBAC via the existing ``payments.reports.read``.

**Off-books boundary (project rule):** these tools expose the *collection
axis only* (gross collected / refunded). They deliberately drop the
receivable / patient-credit figures from the underlying summary, because
"what is still owed" equals the invoiced-minus-collected difference that
clinics keep off-record. The invoice axis lives in ``reports/tools.py``;
the copilot system prompt forbids surfacing the difference between them.
"""

from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.agents import AgentContext, Tool, ToolCategory
from app.core.auth.models import Clinic

from .schemas import PaymentMethod
from .service import LedgerService, PaymentReportsService
from .workflow import PaymentWorkflowError, record_payment


class PeriodArgs(BaseModel):
    date_from: date_cls = Field(description="Inicio del periodo (YYYY-MM-DD).")
    date_to: date_cls = Field(description="Fin del periodo (YYYY-MM-DD).")


class AllocationArg(BaseModel):
    target_type: Literal["budget", "on_account"]
    target_id: UUID | None = Field(
        default=None, description="Id del presupuesto (solo target_type=budget)."
    )
    amount: Decimal = Field(gt=0)


class RecordPaymentArgs(BaseModel):
    patient_id: UUID
    amount: Decimal = Field(gt=0)
    method: PaymentMethod
    payment_date: date_cls
    allocations: list[AllocationArg] = Field(
        min_length=1,
        description="Reparto del cobro; la suma debe igualar amount.",
    )
    reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = Field(
        default=None,
        max_length=100,
        description="Clave de idempotencia: repetir la llamada con la misma clave devuelve el cobro ya registrado.",
    )


class PatientPaymentHistoryArgs(BaseModel):
    patient_id: UUID
    limit: int = Field(default=20, ge=1, le=50, description="Últimos N movimientos.")


async def _currency(ctx: AgentContext) -> str:
    return (await ctx.db.scalar(select(Clinic.currency).where(Clinic.id == ctx.clinic_id))) or "EUR"


async def _payments_summary(ctx: AgentContext, params: PeriodArgs) -> dict:
    currency = await _currency(ctx)
    s = await PaymentReportsService.summary(
        ctx.db, ctx.clinic_id, currency, params.date_from, params.date_to
    )
    # Collection axis only — drop patient_credit_total / clinic_receivable_total.
    return {
        "date_from": params.date_from,
        "date_to": params.date_to,
        "currency": s.currency,
        "total_collected": s.total_collected,
        "total_refunded": s.total_refunded,
        "net_collected": s.net_collected,
        "payment_count": s.payment_count,
        "refund_count": s.refund_count,
    }


async def _collections_by_method(ctx: AgentContext, params: PeriodArgs) -> dict:
    rows = await PaymentReportsService.by_method(
        ctx.db, ctx.clinic_id, params.date_from, params.date_to
    )
    return {"methods": [{"method": r.method, "total": r.total, "count": r.count} for r in rows]}


async def _record_payment(ctx: AgentContext, params: RecordPaymentArgs) -> dict:
    currency = await _currency(ctx)
    try:
        payment = await record_payment(
            ctx.db,
            clinic_id=ctx.clinic_id,
            currency=currency,
            patient_id=params.patient_id,
            amount=params.amount,
            method=params.method,
            payment_date=params.payment_date,
            recorded_by=ctx.supervisor_id,
            allocations=[a.model_dump() for a in params.allocations],
            reference=params.reference,
            notes=params.notes,
            idempotency_key=params.idempotency_key,
        )
    except PaymentWorkflowError as e:
        return {"error": "workflow_error", "detail": str(e)}
    return {
        "id": payment.id,
        "amount": payment.amount,
        "currency": payment.currency,
        "method": payment.method,
        "payment_date": payment.payment_date,
    }


async def _patient_payment_history(ctx: AgentContext, params: PatientPaymentHistoryArgs) -> dict:
    currency = await _currency(ctx)
    ledger = await LedgerService.get_patient_ledger(
        ctx.db, ctx.clinic_id, params.patient_id, currency
    )
    # Collection axis only: payments + refunds. The ledger's earned /
    # patient_credit / clinic_receivable figures are the paid-vs-earned
    # diff this module never surfaces (off-books rule) — drop them.
    movements = [e for e in ledger.timeline if e.entry_type in ("payment", "refund")]
    movements.sort(key=lambda e: e.occurred_at, reverse=True)
    return {
        "patient_id": params.patient_id,
        "currency": ledger.currency,
        "total_paid": ledger.total_paid,
        "on_account_balance": ledger.on_account_balance,
        "movements": [
            {
                "entry_type": e.entry_type,
                "occurred_at": e.occurred_at,
                "amount": e.amount,
                "method_or_reason": e.description,
            }
            for e in movements[: params.limit]
        ],
    }


def get_tools() -> list[Tool]:
    return [
        Tool(
            name="payments_summary",
            description=(
                "Resumen de cobros de un periodo: cobrado, devuelto y neto. "
                "Solo eje cobro (no incluye facturación ni saldo pendiente)."
            ),
            parameters=PeriodArgs,
            handler=_payments_summary,
            permissions=["payments.reports.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="collections_by_method",
            description="Desglose de lo cobrado por método de pago en un periodo (eje cobro).",
            parameters=PeriodArgs,
            handler=_collections_by_method,
            permissions=["payments.reports.read"],
            category=ToolCategory.READ,
        ),
        Tool(
            name="record_payment",
            description=(
                "Registrar un cobro de un paciente con su reparto "
                "(presupuesto/s o a cuenta). La suma de allocations debe "
                "igualar el importe. Requiere confirmación del usuario."
            ),
            parameters=RecordPaymentArgs,
            handler=_record_payment,
            permissions=["payments.record.write"],
            category=ToolCategory.WRITE,
        ),
        Tool(
            name="patient_payment_history",
            description=(
                "Historial de cobros y devoluciones de un paciente (eje "
                "cobro: total pagado, saldo a cuenta y últimos movimientos). "
                "No incluye facturación ni saldo pendiente."
            ),
            parameters=PatientPaymentHistoryArgs,
            handler=_patient_payment_history,
            permissions=["payments.record.read"],
            category=ToolCategory.READ,
        ),
    ]
