"""Budget ↔ invoice bridge (issue #178, ADR 0019).

Rule: *money allocated to a budget is money for that budget's invoices.*
Whenever a payment's allocations change (``payment.allocated``) or an
invoice is issued from a budget, billing reconciles its own
``invoice_payments`` rows so the invoice axis mirrors the allocation
axis — FIFO over the budget's open invoices, capped by each balance
due, inside the caller's transaction.

Everything here is idempotent: it compares the *objective* (Σ budget
allocations of the payment) with the *current* imputations and only
moves the difference. Payments allocated ``on_account`` are left alone
by design (ADR 0010) — they are the patient's credit until reassigned.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.budget.models import Budget
from app.modules.payments.models import PaymentAllocation

from .models import Invoice, InvoicePayment
from .service import compute_paid_summary
from .workflow import InvoiceWorkflowService

ZERO = Decimal("0.00")


async def lock_budget(db: AsyncSession, clinic_id: UUID, budget_id: UUID) -> None:
    """Serialize every imputation touching ``budget_id``.

    Lock order everywhere is *budget row → invoice rows* so two cobros
    on the same budget (one from the invoice page, one from the quote)
    can't deadlock across each other's invoice locks.
    """
    await db.execute(
        select(Budget.id)
        .where(Budget.id == budget_id, Budget.clinic_id == clinic_id)
        .with_for_update()
    )


async def _open_invoices(
    db: AsyncSession, clinic_id: UUID, budget_id: UUID, prefer_invoice_id: UUID | None
) -> list[Invoice]:
    """Issued/partial invoices of a budget, locked, in imputation order.

    Rows are locked in a stable order (issue_date, created_at, id); the
    preferred invoice — the one the user is collecting on — is then
    moved to the front so the cobro lands where reception expects it,
    remainder FIFO.
    """
    result = await db.execute(
        select(Invoice)
        .where(
            Invoice.clinic_id == clinic_id,
            Invoice.budget_id == budget_id,
            Invoice.status.in_(("issued", "partial")),
            Invoice.credit_note_for_id.is_(None),
            Invoice.deleted_at.is_(None),
        )
        .order_by(Invoice.issue_date, Invoice.created_at, Invoice.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    invoices = list(result.scalars().all())
    if prefer_invoice_id is not None:
        invoices.sort(key=lambda inv: inv.id != prefer_invoice_id)  # stable: preferred first
    return invoices


async def reconcile_payment(
    db: AsyncSession,
    *,
    clinic_id: UUID,
    payment_id: UUID,
    actor_id: UUID,
    prefer_invoice_id: UUID | None = None,
) -> None:
    """Make ``invoice_payments`` for ``payment_id`` mirror its budget allocations.

    For every budget the payment targets *or used to target* (still has
    links to that budget's invoices): impute the shortfall FIFO over the
    budget's open invoices, or unlink the excess LIFO. Invoices whose
    ``budget_id`` is NULL (manual invoices linked by the billing
    orchestrator) are never touched. Recomputes the status of every
    invoice whose links changed.
    """
    objective_rows = await db.execute(
        select(PaymentAllocation.budget_id, func.sum(PaymentAllocation.amount))
        .where(
            PaymentAllocation.clinic_id == clinic_id,
            PaymentAllocation.payment_id == payment_id,
            PaymentAllocation.target_type == "budget",
        )
        .group_by(PaymentAllocation.budget_id)
    )
    objective: dict[UUID, Decimal] = {row[0]: row[1] for row in objective_rows.all()}

    linked_rows = await db.execute(
        select(InvoicePayment, Invoice.budget_id)
        .join(Invoice, Invoice.id == InvoicePayment.invoice_id)
        .where(
            InvoicePayment.clinic_id == clinic_id,
            InvoicePayment.payment_id == payment_id,
            Invoice.budget_id.is_not(None),
        )
        .order_by(InvoicePayment.created_at, InvoicePayment.id)
    )
    linked: dict[UUID, list[InvoicePayment]] = defaultdict(list)
    for link, budget_id in linked_rows.all():
        linked[budget_id].append(link)

    touched: set[UUID] = set()
    for budget_id in sorted(objective.keys() | linked.keys()):  # stable lock order
        await lock_budget(db, clinic_id, budget_id)
        target = objective.get(budget_id, ZERO)
        current = sum((link.amount for link in linked[budget_id]), ZERO)

        if target > current:
            remaining = target - current
            for invoice in await _open_invoices(db, clinic_id, budget_id, prefer_invoice_id):
                _, balance_due = await compute_paid_summary(db, clinic_id, invoice.id)
                take = min(remaining, balance_due)
                if take <= ZERO:
                    continue
                db.add(
                    InvoicePayment(
                        clinic_id=clinic_id,
                        invoice_id=invoice.id,
                        payment_id=payment_id,
                        amount=take,
                        created_by=actor_id,
                    )
                )
                touched.add(invoice.id)
                remaining -= take
                if remaining <= ZERO:
                    break
            # Anything left stays on the budget until more of it is invoiced.

        elif target < current:
            excess = current - target
            for link in reversed(linked[budget_id]):  # LIFO
                if excess <= ZERO:
                    break
                touched.add(link.invoice_id)
                if link.amount <= excess:
                    excess -= link.amount
                    await db.delete(link)
                else:
                    link.amount -= excess
                    excess = ZERO

    if not touched:
        return
    await db.flush()

    invoices = await db.execute(select(Invoice).where(Invoice.id.in_(list(touched))))
    for invoice in invoices.scalars():
        await InvoiceWorkflowService.recalc_invoice_status(db, invoice, actor_id=actor_id)


async def sweep_budget_into_invoice(db: AsyncSession, *, invoice: Invoice, actor_id: UUID) -> None:
    """On issue: pull anticipos already collected on the budget into this invoice.

    Reconciles every payment that has an allocation to ``invoice.budget_id``,
    oldest first, preferring the freshly issued invoice. No-op for
    invoices without a budget.
    """
    if invoice.budget_id is None:
        return
    rows = await db.execute(
        select(PaymentAllocation.payment_id)
        .where(
            PaymentAllocation.clinic_id == invoice.clinic_id,
            PaymentAllocation.budget_id == invoice.budget_id,
            PaymentAllocation.target_type == "budget",
        )
        .group_by(PaymentAllocation.payment_id)
        .order_by(func.min(PaymentAllocation.created_at))
    )
    for (payment_id,) in rows.all():
        await reconcile_payment(
            db,
            clinic_id=invoice.clinic_id,
            payment_id=payment_id,
            actor_id=actor_id,
            prefer_invoice_id=invoice.id,
        )
