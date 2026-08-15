"""Budget workflow service - state machine and status transitions."""

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus

from .models import Budget, BudgetAccessLog, BudgetSignature
from .pricing import allocate_global_discount, net_line_amount
from .service import BudgetHistoryService

logger = logging.getLogger(__name__)

# Valid status transitions. ``completed`` is no longer a reachable
# status — kept as a no-op terminal entry so existing rows persisted
# from older versions still satisfy the can_transition lookup
# without surfacing in any new flow.
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["sent", "accepted", "rejected", "cancelled"],
    "sent": ["accepted", "rejected", "expired", "cancelled"],
    "accepted": ["cancelled"],
    "completed": [],  # Legacy terminal state — no new transitions land here
    "rejected": [],  # Terminal state
    "expired": [],  # Terminal state
    "cancelled": [],  # Terminal state
}

# Public-link auth method values stored in ``Budget.public_auth_method``.
PUBLIC_AUTH_METHODS: set[str] = {"phone_last4", "dob", "manual_code", "none"}

# Patient-facing rejection reasons (closed catalogue from the public link).
PUBLIC_REJECTION_REASONS: set[str] = {"price", "time", "second_opinion", "other"}

# Lockout / rate-limit policy. See ADR 0006.
PUBLIC_AUTH_FAIL_LIMIT_WINDOW = 5  # failures inside the rolling window
PUBLIC_AUTH_FAIL_WINDOW = timedelta(minutes=15)
PUBLIC_AUTH_TOTAL_FAIL_LOCKOUT = 10  # total failures → permanent token lock
PUBLIC_SESSION_TTL = timedelta(minutes=30)

# Default budget validity period when the clinic has no override.
DEFAULT_BUDGET_VALIDITY_DAYS = 30
# Default plan auto-close window after the budget has expired.
DEFAULT_PLAN_AUTO_CLOSE_DAYS = 30


def _hash_password(plaintext: str) -> str:
    """Hash a manual-code with bcrypt. Returns the encoded hash string."""
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(plaintext: str, hashed: str) -> bool:
    """Constant-time bcrypt verification. False on any error."""
    if not hashed:
        return False
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _hash_ip(raw_ip: str | None) -> str:
    """SHA-256 of the requester IP (privacy-preserving). Empty string
    when no IP is available (e.g. unit tests)."""
    payload = (raw_ip or "").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def _resolve_clinic_settings(db: AsyncSession, clinic_id: UUID) -> dict:
    """Read ``clinic.settings`` JSONB for budget-related toggles.

    Implemented with raw SQL to avoid importing the auth.Clinic model
    (which is core, but the lookup is settings-specific and we want a
    single small read).
    """
    row = (
        await db.execute(
            text("SELECT settings FROM clinics WHERE id = :id"),
            {"id": clinic_id},
        )
    ).first()
    return (row.settings if row and row.settings else {}) or {}


class BudgetWorkflowError(Exception):
    """Exception for workflow validation errors."""

    pass


class BudgetWorkflowService:
    """Service for budget status transitions and workflow operations."""

    @staticmethod
    def can_transition(current_status: str, new_status: str) -> bool:
        """Check if a status transition is valid."""
        allowed = VALID_TRANSITIONS.get(current_status, [])
        return new_status in allowed

    @staticmethod
    async def send_budget(
        db: AsyncSession,
        budget: Budget,
        sent_by: UUID,
        send_method: str = "manual",  # "manual" or "email"
        recipient_email: str | None = None,
        custom_message: str | None = None,
    ) -> Budget:
        """Mark budget as sent to patient.

        Args:
            db: Database session.
            budget: Budget to send.
            sent_by: User ID who triggered the send.
            send_method: How it was sent ("manual" for printed/handed, "email" for email).
            recipient_email: Email address if sent by email.
        """
        if not BudgetWorkflowService.can_transition(budget.status, "sent"):
            raise BudgetWorkflowError(f"Cannot send budget from status '{budget.status}'")

        # Check budget has items
        if not budget.items:
            raise BudgetWorkflowError("Cannot send empty budget")

        previous_status = budget.status
        budget.status = "sent"

        # Add history
        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="status_changed",
            changed_by=sent_by,
            previous_state={"status": previous_status},
            new_state={"status": "sent"},
        )

        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="sent",
            changed_by=sent_by,
            new_state={
                "sent_at": datetime.now(UTC).isoformat(),
                "send_method": send_method,
                "recipient_email": recipient_email,
            },
        )

        await db.flush()

        # Publish event for notifications + timeline modules
        await event_bus.publish(
            EventType.BUDGET_SENT,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "budget_number": budget.budget_number,
                "total": str(budget.total) if budget.total is not None else None,
                "send_method": send_method,
                "recipient_email": recipient_email,
                "custom_message": custom_message,
            },
        )

        return budget

    @staticmethod
    async def accept_budget(
        db: AsyncSession,
        budget: Budget,
        signature_data: dict,
        accepted_by: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
        accepted_via: str = "manual",
    ) -> Budget:
        """Accept budget with signature.

        Args:
            accepted_via: ``remote_link`` | ``in_clinic`` | ``manual``.
                Persisted on ``Budget.accepted_via`` so reception can
                see how each acceptance was captured without joining
                signatures.
        """
        if not BudgetWorkflowService.can_transition(budget.status, "accepted"):
            raise BudgetWorkflowError(f"Cannot accept budget from status '{budget.status}'")

        # Check budget has items
        if not budget.items:
            raise BudgetWorkflowError("Cannot accept empty budget")

        previous_status = budget.status
        budget.status = "accepted"
        budget.accepted_via = accepted_via

        # Create signature record
        signature = BudgetSignature(
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            signature_type="full_acceptance",
            signed_items=[str(item.id) for item in budget.items],
            signed_by_name=signature_data["signed_by_name"],
            signed_by_email=signature_data.get("signed_by_email"),
            relationship_to_patient=signature_data.get("relationship_to_patient", "patient"),
            signature_method=signature_data.get("signature_method", "click_accept"),
            signature_data=signature_data.get("signature_data"),
            ip_address=ip_address,
            user_agent=user_agent,
            signed_at=datetime.now(UTC),
        )
        db.add(signature)

        # Add history
        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="status_changed",
            changed_by=accepted_by,
            previous_state={"status": previous_status},
            new_state={"status": "accepted"},
        )

        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="signed",
            changed_by=accepted_by,
            new_state={
                "signature_type": "full_acceptance",
                "signed_by": signature_data["signed_by_name"],
            },
        )

        await db.flush()

        # Render the signed PDF once and persist its SHA-256 hash on
        # the signature row. Lets compliance tooling later detect any
        # tampering with stored / re-rendered PDFs. Best-effort:
        # WeasyPrint failures (e.g. missing system fonts in dev) must
        # not block the acceptance — log and continue.
        try:
            from .pdf import BudgetPDFService

            clinic_row = await db.execute(
                text(
                    "SELECT id, name, address, phone, email, settings, "
                    "tax_id, legal_name FROM clinics WHERE id = :id"
                ),
                {"id": budget.clinic_id},
            )
            clinic = clinic_row.first()
            if clinic is not None:
                clinic_settings = (
                    clinic.settings if isinstance(clinic.settings, dict) else {}
                ) or {}
                locale = str(clinic_settings.get("communication_language") or "es")
                # Re-fetch budget with items eagerly loaded for the PDF.
                from sqlalchemy.orm import selectinload

                from .models import Budget as _Budget

                hydrated = (
                    await db.execute(
                        select(_Budget)
                        .options(selectinload(_Budget.items))
                        .where(_Budget.id == budget.id)
                    )
                ).scalar_one_or_none()
                if hydrated is not None:
                    pdf_bytes = await BudgetPDFService.generate_pdf(
                        hydrated,
                        clinic,  # type: ignore[arg-type]
                        is_preview=False,
                        locale=locale,
                        signature=signature,
                    )
                    signature.document_hash = BudgetPDFService.generate_pdf_hash(pdf_bytes)
                    await db.flush()
        except Exception as exc:
            logger.warning(
                "Could not compute document_hash for budget %s: %s",
                budget.id,
                exc,
            )

        plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
        # Per-line snapshot so subscribers (treatment_plan) can reprice
        # what the patient actually agreed to pay without reading budget
        # rows: net_amount is ex-tax, after line discount + prorated
        # global discount (see pricing.allocate_global_discount).
        shares = allocate_global_discount(
            budget.global_discount_type, budget.global_discount_value, budget.items
        )
        items_snapshot = [
            {
                "budget_item_id": str(item.id),
                "treatment_id": str(item.treatment_id) if item.treatment_id else None,
                "catalog_item_id": str(item.catalog_item_id),
                "quantity": item.quantity,
                "net_amount": str(net_line_amount(item, share)),
            }
            for item, share in zip(budget.items, shares, strict=True)
        ]
        await event_bus.publish(
            EventType.BUDGET_ACCEPTED,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "budget_number": budget.budget_number,
                "total": str(budget.total) if budget.total is not None else None,
                "accepted_by": str(accepted_by),
                "accepted_via": accepted_via,
                "plan_id": str(plan_id) if plan_id else None,
                "items": items_snapshot,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

        return budget

    @staticmethod
    async def reject_budget(
        db: AsyncSession,
        budget: Budget,
        rejected_by: UUID | None = None,
        reason: str | None = None,
        note: str | None = None,
        signature_data: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Budget:
        """Reject a budget.

        Persists the rejection reason in ``Budget.rejection_reason`` and
        ``Budget.rejection_note`` (in addition to the history entry) so
        analytics queries do not need to parse history JSON. Publishes
        ``budget.rejected`` so the treatment_plan module can close the
        companion plan with ``closure_reason='rejected_by_patient'``.
        """
        if not BudgetWorkflowService.can_transition(budget.status, "rejected"):
            raise BudgetWorkflowError(f"Cannot reject budget from status '{budget.status}'")

        previous_status = budget.status
        budget.status = "rejected"
        if reason is not None:
            budget.rejection_reason = reason
        if note is not None:
            budget.rejection_note = note

        # Create signature record if provided
        if signature_data:
            signature = BudgetSignature(
                clinic_id=budget.clinic_id,
                budget_id=budget.id,
                signature_type="rejection",
                signed_by_name=signature_data["signed_by_name"],
                signed_by_email=signature_data.get("signed_by_email"),
                relationship_to_patient=signature_data.get("relationship_to_patient", "patient"),
                signature_method=signature_data.get("signature_method", "click_accept"),
                signature_data=signature_data.get("signature_data"),
                ip_address=ip_address,
                user_agent=user_agent,
                signed_at=datetime.now(UTC),
            )
            db.add(signature)

        # Add history
        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="status_changed",
            changed_by=rejected_by or budget.created_by,
            previous_state={"status": previous_status},
            new_state={"status": "rejected", "reason": reason, "note": note},
        )

        await db.flush()

        plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
        await event_bus.publish(
            EventType.BUDGET_REJECTED,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "budget_number": budget.budget_number,
                "plan_id": str(plan_id) if plan_id else None,
                "rejection_reason": reason,
                "rejection_note": note,
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

        return budget

    @staticmethod
    async def cancel_budget(
        db: AsyncSession,
        budget: Budget,
        cancelled_by: UUID,
        reason: str | None = None,
        publish_event: bool = True,
    ) -> Budget:
        """Cancel a budget.

        Publishes ``budget.cancelled`` so the companion pending plan can
        reopen to ``draft`` (issue #162). ``publish_event=False`` is for
        callers that already own the plan transition — namely
        ``TreatmentPlanService.reopen()``, which cancels the budget from
        inside its own transaction: an echo event there would make the
        handler write the plan row the publisher holds locked → hang.
        """
        if not BudgetWorkflowService.can_transition(budget.status, "cancelled"):
            raise BudgetWorkflowError(f"Cannot cancel budget from status '{budget.status}'")

        previous_status = budget.status
        budget.status = "cancelled"

        # Add history
        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="status_changed",
            changed_by=cancelled_by,
            previous_state={"status": previous_status},
            new_state={"status": "cancelled", "reason": reason},
        )

        await db.flush()

        if publish_event:
            # Safe pre-commit publish: our transaction only holds locks
            # on budgets/budget_history; the handler writes only the
            # (long-committed) treatment_plans row.
            plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
            await event_bus.publish(
                EventType.BUDGET_CANCELLED,
                {
                    "clinic_id": str(budget.clinic_id),
                    "budget_id": str(budget.id),
                    "patient_id": str(budget.patient_id),
                    "budget_number": budget.budget_number,
                    "plan_id": str(plan_id) if plan_id else None,
                    "reason": reason,
                    "cancelled_by": str(cancelled_by),
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )

        return budget

    @staticmethod
    async def check_expired_budgets(
        db: AsyncSession,
        clinic_id: UUID,
    ) -> list[Budget]:
        """Check for and mark expired budgets.

        Should be called periodically (e.g., daily cron job).
        Draft and sent budgets can expire (accepted budgets don't expire).
        Publishes ``budget.expired`` for each expired budget so the
        treatment_plan module can keep its pending plans visible with a
        "presupuesto caducado" badge until the auto-close cron kicks in.
        """
        from datetime import date

        today = date.today()

        # Find draft or sent budgets past their valid_until date
        result = await db.execute(
            select(Budget).where(
                Budget.clinic_id == clinic_id,
                Budget.status.in_(["draft", "sent"]),
                Budget.valid_until.isnot(None),
                Budget.valid_until < today,
                Budget.deleted_at.is_(None),
            )
        )

        expired_budgets = list(result.scalars().all())

        for budget in expired_budgets:
            previous_status = budget.status
            budget.status = "expired"

            # Add history (use creator as fallback)
            await BudgetHistoryService.add_entry(
                db,
                clinic_id=budget.clinic_id,
                budget_id=budget.id,
                action="status_changed",
                changed_by=budget.created_by,
                previous_state={"status": previous_status},
                new_state={"status": "expired", "expired_at": today.isoformat()},
                notes="Automatically expired due to validity period",
            )

        await db.flush()

        # Publish events for subscribers (treatment_plan, patient_timeline).
        for budget in expired_budgets:
            plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
            days_overdue = (today - budget.valid_until).days if budget.valid_until else None
            await event_bus.publish(
                EventType.BUDGET_EXPIRED,
                {
                    "clinic_id": str(budget.clinic_id),
                    "budget_id": str(budget.id),
                    "patient_id": str(budget.patient_id),
                    "budget_number": budget.budget_number,
                    "plan_id": str(plan_id) if plan_id else None,
                    "valid_until": budget.valid_until.isoformat() if budget.valid_until else None,
                    "days_overdue": days_overdue,
                    "occurred_at": datetime.now(UTC).isoformat(),
                },
            )

        return expired_budgets

    # ---------------------------------------------------------------------
    # Renegotiation, public-link helpers and resend
    # ---------------------------------------------------------------------

    @staticmethod
    async def _lookup_plan(db: AsyncSession, budget_id: UUID):
        """Reverse-lookup the plan (id, status) that references a budget.

        Implemented with raw SQL to avoid importing the
        ``treatment_plan`` ORM model from this module (ADR 0003).
        Deliberately does NOT walk the ``parent_budget_id`` chain: a
        stale old version must keep resolving to no plan once the link
        has moved on, or e.g. rejecting V1 could close a plan living
        on V2.
        """
        row = (
            await db.execute(
                text(
                    "SELECT id, status FROM treatment_plans "
                    "WHERE budget_id = :bid AND deleted_at IS NULL "
                    "LIMIT 1"
                ),
                {"bid": budget_id},
            )
        ).first()
        return row

    @staticmethod
    async def _lookup_plan_id(db: AsyncSession, budget_id: UUID) -> UUID | None:
        """Reverse-lookup the id of the plan that references a budget."""
        row = await BudgetWorkflowService._lookup_plan(db, budget_id)
        return row.id if row else None

    @staticmethod
    async def cancel_for_renegotiation(
        db: AsyncSession,
        budget: Budget,
        cancelled_by: UUID,
    ) -> Budget:
        """Cancel a sent budget so reception can renegotiate.

        Publishes ``budget.renegotiated`` carrying ``plan_id`` so the
        treatment_plan handler can reopen the companion plan back to
        ``draft``. The reopen is event-driven specifically because
        ``treatment_plan`` is not in budget's ``manifest.depends`` —
        the reverse direction is correctly the bus.
        """
        if not BudgetWorkflowService.can_transition(budget.status, "cancelled"):
            raise BudgetWorkflowError(f"Cannot renegotiate budget in status '{budget.status}'")

        previous_status = budget.status
        budget.status = "cancelled"

        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=budget.id,
            action="status_changed",
            changed_by=cancelled_by,
            previous_state={"status": previous_status},
            new_state={"status": "cancelled", "reason": "renegotiation"},
        )
        await db.flush()

        plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
        await event_bus.publish(
            EventType.BUDGET_RENEGOTIATED,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "plan_id": str(plan_id) if plan_id else None,
                "version": budget.version,
                "cancelled_at": datetime.now(UTC).isoformat(),
                "cancelled_by": str(cancelled_by),
            },
        )
        return budget

    @staticmethod
    async def mark_viewed(
        db: AsyncSession,
        budget: Budget,
        ip_hash: str | None = None,
    ) -> Budget:
        """Idempotently record the first time the patient opened the
        public link. Publishes ``budget.viewed`` only on the first call.
        """
        if budget.viewed_at is not None:
            return budget
        budget.viewed_at = datetime.now(UTC)
        await db.flush()
        plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
        await event_bus.publish(
            EventType.BUDGET_VIEWED,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "plan_id": str(plan_id) if plan_id else None,
                "viewed_at": budget.viewed_at.isoformat(),
                "ip_hash": ip_hash,
            },
        )
        return budget

    @staticmethod
    async def send_reminder(
        db: AsyncSession,
        budget: Budget,
        milestone_days: int,
    ) -> Budget:
        """Stamp a reminder dispatch and publish ``budget.reminder_sent``.

        Does not actually send the email — the notifications module
        subscribes to the event and renders the message.
        """
        budget.last_reminder_sent_at = datetime.now(UTC)
        await db.flush()
        plan_id = await BudgetWorkflowService._lookup_plan_id(db, budget.id)
        await event_bus.publish(
            EventType.BUDGET_REMINDER_SENT,
            {
                "clinic_id": str(budget.clinic_id),
                "budget_id": str(budget.id),
                "patient_id": str(budget.patient_id),
                "plan_id": str(plan_id) if plan_id else None,
                "budget_number": budget.budget_number,
                "milestone_days": milestone_days,
                "sent_at": budget.last_reminder_sent_at.isoformat(),
            },
        )
        return budget

    @staticmethod
    async def set_public_code(
        db: AsyncSession,
        budget: Budget,
        code: str,
    ) -> Budget:
        """Configure the manual code for a budget whose patient has no
        phone or DOB on file. The code is hashed (bcrypt) so the
        plaintext never lives at rest. Reception is expected to share
        the code with the patient verbally.
        """
        if not (4 <= len(code) <= 6) or not code.isdigit():
            raise BudgetWorkflowError("Manual code must be 4-6 numeric digits")
        budget.public_auth_method = "manual_code"
        budget.public_auth_secret_hash = _hash_password(code)
        await db.flush()
        return budget

    @staticmethod
    async def unlock_public(
        db: AsyncSession,
        budget: Budget,
    ) -> Budget:
        """Clear ``public_locked_at`` so the existing token works again."""
        budget.public_locked_at = None
        await db.flush()
        return budget

    @staticmethod
    async def resolve_public_auth_method(
        db: AsyncSession,
        clinic_id: UUID,
        patient_id: UUID,
        clinic_settings: dict | None = None,
    ) -> str:
        """Determine the auth method for a new public link based on the
        patient record and the clinic toggle.

        Cascade (see ADR 0006):

        1. Clinic opt-out (``budget_public_auth_disabled=true``) → ``none``.
        2. Patient phone has ≥4 digits → ``phone_last4``.
        3. Patient has ``date_of_birth`` → ``dob``.
        4. Otherwise → ``manual_code`` (caller must call
           ``set_public_code`` before sending the budget).
        """
        settings = (
            clinic_settings
            if clinic_settings is not None
            else (await _resolve_clinic_settings(db, clinic_id))
        )
        if settings.get("budget_public_auth_disabled"):
            return "none"

        # Patient lookup via ORM — patients is in budget.depends.
        from app.modules.patients.models import Patient

        patient = await db.get(Patient, patient_id)
        if patient is None:
            return "manual_code"
        digits = "".join(ch for ch in (patient.phone or "") if ch.isdigit())
        if len(digits) >= 4:
            return "phone_last4"
        if patient.date_of_birth is not None:
            return "dob"
        return "manual_code"

    @staticmethod
    async def verify_public_access(
        db: AsyncSession,
        budget: Budget,
        method: str,
        value: str,
        ip_hash: str,
    ) -> tuple[bool, str | None]:
        """Validate a verification attempt for the public link.

        Returns ``(ok, error_code)``. Error codes:

        - ``locked``  — token is permanently locked (``public_locked_at`` set).
        - ``expired`` — budget past ``valid_until``.
        - ``rate_limited`` — too many attempts in the rolling window.
        - ``method_mismatch`` — caller used the wrong method.
        - ``invalid`` — wrong value.

        On the 10th total failed attempt the function sets
        ``public_locked_at`` and returns ``(False, "locked")``.
        """
        if budget.public_locked_at is not None:
            return False, "locked"
        if budget.valid_until is not None and budget.valid_until < datetime.now(UTC).date():
            return False, "expired"
        if method != budget.public_auth_method:
            return False, "method_mismatch"

        # Rate limit: failures in the rolling window.
        now = datetime.now(UTC)
        window_start = now - PUBLIC_AUTH_FAIL_WINDOW
        recent_fail_count = (
            await db.execute(
                select(func.count(BudgetAccessLog.id)).where(
                    BudgetAccessLog.budget_id == budget.id,
                    BudgetAccessLog.attempted_at >= window_start,
                    BudgetAccessLog.success.is_(False),
                )
            )
        ).scalar() or 0
        if recent_fail_count >= PUBLIC_AUTH_FAIL_LIMIT_WINDOW:
            return False, "rate_limited"

        ok = await BudgetWorkflowService._compare_method_value(db, budget, method, value)

        # Log the attempt regardless of outcome.
        db.add(
            BudgetAccessLog(
                budget_id=budget.id,
                ip_hash=ip_hash,
                success=ok,
                method_attempted=method,
            )
        )
        await db.flush()

        if not ok:
            total_fail_count = (
                await db.execute(
                    select(func.count(BudgetAccessLog.id)).where(
                        BudgetAccessLog.budget_id == budget.id,
                        BudgetAccessLog.success.is_(False),
                    )
                )
            ).scalar() or 0
            if total_fail_count >= PUBLIC_AUTH_TOTAL_FAIL_LOCKOUT:
                budget.public_locked_at = now
                await db.flush()
                return False, "locked"
            return False, "invalid"
        return True, None

    @staticmethod
    async def _compare_method_value(
        db: AsyncSession,
        budget: Budget,
        method: str,
        value: str,
    ) -> bool:
        """Constant-time-ish comparison of the verification value
        against the patient record / hashed code.
        """
        if method == "none":
            return True
        if method == "manual_code":
            return _verify_password(value, budget.public_auth_secret_hash or "")

        from app.modules.patients.models import Patient

        patient = await db.get(Patient, budget.patient_id)
        if patient is None:
            return False
        if method == "phone_last4":
            digits = "".join(ch for ch in (patient.phone or "") if ch.isdigit())
            if len(digits) < 4:
                return False
            value_digits = "".join(ch for ch in value if ch.isdigit())
            return secrets.compare_digest(digits[-4:], value_digits)
        if method == "dob":
            if patient.date_of_birth is None:
                return False
            return secrets.compare_digest(patient.date_of_birth.isoformat(), value.strip())
        return False

    @staticmethod
    async def clone_to_new_draft(
        db: AsyncSession,
        budget: Budget,
        cloned_by: UUID,
    ) -> Budget:
        """Clone a finished (rejected/expired/cancelled) budget to a new
        draft (version+1). Used by reception to "Resend" a budget.

        The new draft inherits the line items, valid window and plan
        snapshots; it gets a fresh ``public_token`` and re-resolves the
        ``public_auth_method`` against the current Patient record.
        """
        from .service import BudgetItemService, BudgetService

        # Refresh the plan-status snapshot from the live plan (the one
        # copied from a terminal budget is stale by definition).
        plan_ref = await BudgetWorkflowService._lookup_plan(db, budget.id)

        new_budget = Budget(
            clinic_id=budget.clinic_id,
            patient_id=budget.patient_id,
            budget_number=budget.budget_number,
            version=budget.version + 1,
            parent_budget_id=budget.id,
            status="draft",
            valid_from=datetime.now(UTC).date(),
            valid_until=budget.valid_until,
            created_by=cloned_by,
            assigned_professional_id=budget.assigned_professional_id,
            global_discount_type=budget.global_discount_type,
            global_discount_value=budget.global_discount_value,
            plan_number_snapshot=budget.plan_number_snapshot,
            plan_status_snapshot=plan_ref.status if plan_ref else budget.plan_status_snapshot,
        )
        # Resolve public auth method against current patient record.
        new_budget.public_auth_method = await BudgetWorkflowService.resolve_public_auth_method(
            db, budget.clinic_id, budget.patient_id
        )
        db.add(new_budget)
        await db.flush()

        # Clone items (snapshot of catalog/treatment refs).
        for item in budget.items:
            await BudgetItemService.create_item(
                db,
                budget.clinic_id,
                new_budget.id,
                {
                    "catalog_item_id": item.catalog_item_id,
                    "quantity": item.quantity,
                    "treatment_id": item.treatment_id,
                    "tooth_number": item.tooth_number,
                    "surfaces": item.surfaces,
                    "unit_price": item.unit_price,
                    "discount_type": item.discount_type,
                    "discount_value": item.discount_value,
                    "vat_type_id": item.vat_type_id,
                    "vat_rate": item.vat_rate,
                    "display_order": item.display_order,
                    "notes": item.notes,
                },
            )
        await BudgetService._recalculate_totals(db, new_budget)

        await BudgetHistoryService.add_entry(
            db,
            clinic_id=budget.clinic_id,
            budget_id=new_budget.id,
            action="created",
            changed_by=cloned_by,
            previous_state={"parent_budget_id": str(budget.id)},
            new_state={"status": "draft", "version": new_budget.version},
            notes="Cloned from budget for resend",
        )
        await db.flush()
        return new_budget
