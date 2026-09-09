"""Invoice workflow service - state machine and status transitions."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType, event_bus

from .hooks import BillingHookRegistry
from .models import Invoice, InvoiceItem

# Valid status transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["issued", "voided"],
    "issued": ["paid", "partial", "cancelled"],
    "partial": ["paid", "cancelled"],
    "paid": [],  # Terminal (can emit credit note)
    "cancelled": [],  # Terminal
    "voided": [],  # Terminal
}


class InvoiceWorkflowError(Exception):
    """Exception for workflow validation errors."""

    pass


class InvoiceWorkflowService:
    """Service for invoice status transitions and workflow operations."""

    @staticmethod
    def can_transition(current_status: str, new_status: str) -> bool:
        """Check if a status transition is valid."""
        allowed = VALID_TRANSITIONS.get(current_status, [])
        return new_status in allowed

    @staticmethod
    def can_edit(invoice: Invoice) -> bool:
        """Check if invoice can be edited."""
        return invoice.status == "draft"

    @staticmethod
    def can_issue(invoice: Invoice) -> bool:
        """Check if invoice can be issued."""
        return invoice.status == "draft" and len(invoice.items) > 0

    @staticmethod
    def can_record_payment(invoice: Invoice) -> bool:
        """Check if payment can be recorded for invoice."""
        return invoice.status in ["issued", "partial"]

    @staticmethod
    def can_void(invoice: Invoice) -> bool:
        """Check if invoice can be voided (before issue)."""
        return invoice.status == "draft"

    @staticmethod
    def can_create_credit_note(invoice: Invoice) -> bool:
        """Check if credit note can be created for invoice.

        Credit notes cannot be created for:
        - Invoices that are not issued/partial/paid
        - Invoices that are already credit notes (rectificativas)
        """
        if invoice.credit_note_for_id is not None:
            return False
        return invoice.status in ["issued", "partial", "paid"]

    @staticmethod
    async def issue_invoice(
        db: AsyncSession,
        invoice: Invoice,
        issued_by: UUID,
        issue_date: date | None = None,
        hook_callback=None,
    ) -> Invoice:
        """Issue an invoice or credit note (transition from draft to issued).

        For regular invoices:
            - Status changes to "issued"
            - balance_due is set to the total amount

        For credit notes (rectificativas):
            - Status changes to "issued"
            - balance_due is NEGATIVE (represents credit in patient's favor)
            - Original invoice status is NOT changed (both documents coexist)
            - Country-specific hooks can modify original invoice if needed

        Args:
            db: Database session
            invoice: Invoice or credit note to issue
            issued_by: User ID issuing the invoice
            issue_date: Issue date (defaults to today)
            hook_callback: Optional compliance hook callback for regular invoices.
                          For credit notes, use on_credit_note_issued hook instead.

        Returns:
            Updated invoice with "issued" status

        Raises:
            InvoiceWorkflowError: If transition is not valid

        See Also:
            create_credit_note: For creating credit notes in draft status
            hooks.BillingComplianceHook.on_credit_note_issued: For country-specific behavior
        """
        if not InvoiceWorkflowService.can_issue(invoice):
            if invoice.status != "draft":
                raise InvoiceWorkflowError(f"Cannot issue invoice from status '{invoice.status}'")
            if not invoice.items:
                raise InvoiceWorkflowError("Cannot issue empty invoice")

        # Snapshot billing data from patient (drafts don't store it)
        if invoice.billing_name is None:
            from sqlalchemy import select

            from app.modules.patients.models import Patient

            result = await db.execute(select(Patient).where(Patient.id == invoice.patient_id))
            patient = result.scalar_one_or_none()
            if not patient:
                raise InvoiceWorkflowError("Patient not found")

            # Snapshot billing data from patient
            invoice.billing_name = patient.effective_billing_name
            invoice.billing_tax_id = patient.effective_billing_tax_id
            invoice.billing_address = patient.billing_address
            invoice.billing_email = patient.billing_email or patient.email

        # Validate billing data completeness.
        #
        # ``billing_tax_id`` is required by default for plain invoicing, but
        # delegated to the country compliance hook when one is registered
        # for the clinic — Spanish Verifactu, for example, accepts F2
        # simplified invoices without recipient NIF up to 400 €. The hook
        # already ran ``validate_before_issue`` upstream, so when a hook
        # is in charge we trust its decision and skip the strict default.
        billing_errors = []
        if not invoice.billing_name:
            billing_errors.append("billing_name is required")
        if not invoice.billing_tax_id:
            clinic = invoice.clinic
            hook = BillingHookRegistry.get_for_clinic(clinic) if clinic else None
            if hook is None:
                billing_errors.append("billing_tax_id is required (update patient billing info)")
        if billing_errors:
            raise InvoiceWorkflowError(
                f"Cannot issue invoice: incomplete billing data. {', '.join(billing_errors)}"
            )

        # Assign invoice number if not already assigned (drafts don't have numbers)
        if invoice.invoice_number is None:
            from .service import InvoiceNumberService, InvoiceSeriesService

            # Determine series to use
            series_id = invoice.series_id
            if not series_id:
                # Get default series based on invoice type
                series_type = "credit_note" if invoice.credit_note_for_id else "invoice"
                series = await InvoiceSeriesService.get_default_series(
                    db, invoice.clinic_id, series_type
                )
                if not series:
                    raise InvoiceWorkflowError(f"No default {series_type} series configured")
                series_id = series.id

            # Generate number
            invoice_number, sequential_number = await InvoiceNumberService.generate_number(
                db, invoice.clinic_id, series_id
            )
            invoice.invoice_number = invoice_number
            invoice.sequential_number = sequential_number
            invoice.series_id = series_id

        previous_status = invoice.status
        invoice.status = "issued"
        invoice.issue_date = issue_date or date.today()
        invoice.issued_by = issued_by

        # Calculate due date if not set
        if not invoice.due_date:
            from datetime import timedelta

            invoice.due_date = invoice.issue_date + timedelta(days=invoice.payment_term_days)

        # ``total_paid`` and ``balance_due`` are computed on read from
        # ``invoice_payments`` (see ``compute_paid_summary``). No state to
        # initialize here.

        # Execute compliance hook if provided
        if hook_callback:
            compliance_data = await hook_callback(invoice, db)
            if compliance_data:
                invoice.compliance_data = invoice.compliance_data or {}
                invoice.compliance_data.update(compliance_data)

        # Add history
        from .service import InvoiceHistoryService

        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            action="issued",
            changed_by=issued_by,
            previous_state={"status": previous_status},
            new_state={
                "status": "issued",
                "issue_date": invoice.issue_date.isoformat(),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            },
        )

        # =======================================================================
        # Credit Note (Rectificativa) Special Logic
        # =======================================================================
        #
        # When issuing a credit note, the following applies:
        #
        # 1. ORIGINAL INVOICE: Does NOT change status.
        #    - Both invoices are valid fiscal documents that coexist.
        #    - The patient's balance is calculated by summing all invoices.
        #    - This is the standard behavior in most countries (Spain, EU, USA, UK).
        #
        # 2. CREDIT NOTE: Stays in "issued" status with NEGATIVE balance.
        #    - total: negative amount (e.g., -100.00)
        #    - total_paid: 0.00 (nothing has been paid yet)
        #    - balance_due: negative (e.g., -100.00) = credit in patient's favor
        #
        # 3. BALANCE CALCULATION:
        #    - Patient balance = sum of all invoice balance_due values
        #    - Positive = patient owes money
        #    - Negative = clinic owes patient (refund or credit for future)
        #
        # 4. COUNTRY-SPECIFIC BEHAVIOR:
        #    - Some countries (e.g., Mexico, Argentina) may require cancelling
        #      the original invoice. This should be handled by the compliance
        #      hook (on_credit_note_issued) which receives both invoices and
        #      can modify the original invoice's status if required.
        #
        # =======================================================================
        if invoice.credit_note_for_id:
            # Credit note stays in "issued" status. Its negative ``total``
            # already represents the credit in the patient's favour; no
            # cached paid columns exist anymore.

            # Add history to original invoice (informational, no status change)
            from sqlalchemy import select

            result = await db.execute(
                select(Invoice).where(Invoice.id == invoice.credit_note_for_id)
            )
            original_invoice = result.scalar_one_or_none()
            if original_invoice:
                await InvoiceHistoryService.add_entry(
                    db,
                    clinic_id=original_invoice.clinic_id,
                    invoice_id=original_invoice.id,
                    action="credit_note_issued",
                    changed_by=issued_by,
                    previous_state={},
                    new_state={
                        "credit_note_id": str(invoice.id),
                        "credit_note_number": invoice.invoice_number,
                        "credit_note_total": str(invoice.total),
                    },
                    notes="Credit note issued. Original invoice status unchanged.",
                )

        await db.flush()

        await event_bus.publish(
            EventType.INVOICE_ISSUED,
            {
                "clinic_id": str(invoice.clinic_id),
                "invoice_id": str(invoice.id),
                "patient_id": str(invoice.patient_id),
                "invoice_number": invoice.invoice_number,
                "total": str(invoice.total) if invoice.total is not None else None,
                "issued_by": str(issued_by),
                "occurred_at": datetime.now(UTC).isoformat(),
            },
        )

        # Anticipos already collected on the quote land on this invoice
        # now (issue #178). May flip it straight to ``paid``.
        if invoice.credit_note_for_id is None:
            from .payment_bridge import sweep_budget_into_invoice

            await sweep_budget_into_invoice(db, invoice=invoice, actor_id=issued_by)

        return invoice

    @staticmethod
    async def update_billing_party(
        db: AsyncSession,
        invoice: Invoice,
        *,
        new_name: str | None,
        new_tax_id: str | None,
        new_address: dict | None,
        expected_updated_at: datetime | None,
        changed_by: UUID,
    ) -> Invoice:
        """Edit billing-party fields on an issued invoice with compliance gate.

        Drafts: open editing (no fiscal commitment yet).

        Issued + compliance hook present: only allowed when the hook's
        latest fiscal record reports a correctable state. For Verifactu
        that means ``rejected`` / ``failed_validation`` — AEAT never
        registered the original data, so the spec admits Subsanación
        with corrected data. ``accepted`` invoices require a credit
        note instead and are rejected here.

        On success, triggers the compliance hook's regenerate path so
        the user does not have to re-trigger from the compliance queue.
        """

        if expected_updated_at is not None and invoice.updated_at is not None:
            # Treat both as UTC; the DB stores TIMESTAMPTZ so updated_at
            # is timezone-aware. The frontend echoes whatever was served.
            if abs((invoice.updated_at - expected_updated_at).total_seconds()) > 1:
                raise InvoiceWorkflowError("concurrent edit detected — refresh and try again")

        if invoice.status != "draft":
            hook = BillingHookRegistry.get_for_clinic(invoice.clinic) if invoice.clinic else None
            if hook is None:
                raise InvoiceWorkflowError(
                    f"Cannot edit billing party on invoice with status '{invoice.status}'"
                )
            allowed, reason = await hook.can_edit_billing_party(invoice, db)
            if not allowed:
                raise InvoiceWorkflowError(
                    reason or "Edición no permitida por la normativa de cumplimiento de este país."
                )

        previous = {
            "billing_name": invoice.billing_name,
            "billing_tax_id": invoice.billing_tax_id,
            "billing_address": invoice.billing_address,
        }
        if new_name is not None:
            invoice.billing_name = new_name.strip() or None
        if new_tax_id is not None:
            invoice.billing_tax_id = new_tax_id.strip().upper() or None
        if new_address is not None:
            invoice.billing_address = new_address

        from .service import InvoiceHistoryService

        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            action="billing_party_updated",
            changed_by=changed_by,
            previous_state=previous,
            new_state={
                "billing_name": invoice.billing_name,
                "billing_tax_id": invoice.billing_tax_id,
                "billing_address": invoice.billing_address,
            },
        )

        await db.flush()

        # Auto-regenerate compliance record so the user does not have
        # to chase the compliance queue. Drafts have no fiscal record
        # yet; the hook signals a no-op via the default impl.
        if invoice.status != "draft":
            hook = BillingHookRegistry.get_for_clinic(invoice.clinic) if invoice.clinic else None
            if hook is not None:
                regenerated = await hook.regenerate_after_party_change(invoice, db)
                if regenerated:
                    # New dict, not an in-place update: plain JSONB only
                    # persists on reassignment.
                    invoice.compliance_data = {**(invoice.compliance_data or {}), **regenerated}

        return invoice

    @staticmethod
    async def void_invoice(
        db: AsyncSession,
        invoice: Invoice,
        voided_by: UUID,
        reason: str | None = None,
    ) -> Invoice:
        """Void an invoice (only allowed for drafts)."""
        if not InvoiceWorkflowService.can_void(invoice):
            raise InvoiceWorkflowError(f"Cannot void invoice from status '{invoice.status}'")

        previous_status = invoice.status
        invoice.status = "voided"
        invoice.deleted_at = datetime.now(UTC)

        # Add history
        from .service import InvoiceHistoryService, resync_invoiced_quantities_for_invoice

        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=invoice.clinic_id,
            invoice_id=invoice.id,
            action="voided",
            changed_by=voided_by,
            previous_state={"status": previous_status},
            new_state={"status": "voided", "reason": reason},
        )

        await db.flush()
        await resync_invoiced_quantities_for_invoice(db, invoice)

        return invoice

    @staticmethod
    async def recalc_invoice_status(
        db: AsyncSession,
        invoice: Invoice,
        *,
        actor_id: UUID,
    ) -> str:
        """Recalculate ``invoice.status`` from current invoice_payments.

        Called by the billing-side orchestration endpoint (after creating
        a Payment + InvoicePayment via the payments module) and by the
        ``payment.refunded`` event handler. Returns the new status.

        - ``balance_due <= 0`` → ``paid`` (also emits ``INVOICE_PAID``).
        - ``0 < total_paid < total`` → ``partial``.
        - ``total_paid <= 0`` → ``issued`` (no payment registered).
        Never moves a ``draft`` / ``cancelled`` / ``voided`` invoice.
        """
        from .service import InvoiceHistoryService, compute_paid_summary

        total_paid, balance_due = await compute_paid_summary(db, invoice.clinic_id, invoice.id)

        if invoice.status in ("draft", "cancelled", "voided"):
            return invoice.status

        previous_status = invoice.status
        if balance_due <= Decimal("0.00") and invoice.total > 0:
            invoice.status = "paid"
        elif total_paid > 0:
            invoice.status = "partial"
        else:
            invoice.status = "issued"

        if invoice.status != previous_status:
            await InvoiceHistoryService.add_entry(
                db,
                clinic_id=invoice.clinic_id,
                invoice_id=invoice.id,
                action="status_recomputed",
                changed_by=actor_id,
                previous_state={"status": previous_status},
                new_state={
                    "status": invoice.status,
                    "total_paid": str(total_paid),
                    "balance_due": str(balance_due),
                },
            )
            await db.flush()

            if invoice.status == "paid":
                await event_bus.publish(
                    EventType.INVOICE_PAID,
                    {
                        "clinic_id": str(invoice.clinic_id),
                        "invoice_id": str(invoice.id),
                        "patient_id": str(invoice.patient_id),
                        "invoice_number": invoice.invoice_number,
                        "total": str(invoice.total),
                        "total_paid": str(total_paid),
                        "occurred_at": datetime.now(UTC).isoformat(),
                    },
                )

        return invoice.status

    @staticmethod
    async def create_credit_note(
        db: AsyncSession,
        original_invoice: Invoice,
        created_by: UUID,
        reason: str,
        items: list[dict] | None = None,
        series_id: UUID | None = None,
    ) -> Invoice:
        """Create a credit note (rectificativa) for an invoice in draft status.

        The credit note is created in draft status so it can be reviewed and
        edited before being issued via issue_invoice().

        IMPORTANT - Fiscal treatment:
            - The original invoice does NOT change status when the credit note
              is issued. Both documents are valid and coexist.
            - The patient's balance is calculated by summing all invoices
              (original + credit notes). A negative balance means the clinic
              owes the patient (refund or credit for future invoices).
            - This is the standard behavior in most countries (Spain, EU, UK, USA).
            - For countries that require cancelling the original invoice
              (e.g., Mexico, Argentina), use the on_credit_note_issued hook.

        Args:
            db: Database session
            original_invoice: Invoice to rectify
            created_by: User creating the credit note
            reason: Reason for the credit note
            items: Optional list of items to rectify (partial credit note).
                   If None, rectifies the entire invoice amount.
            series_id: Optional series ID for credit note (uses default if not provided)

        Returns:
            New credit note invoice in draft status

        See Also:
            issue_invoice: To issue the credit note after editing
            hooks.BillingComplianceHook.on_credit_note_issued: For country-specific behavior
        """
        if not InvoiceWorkflowService.can_create_credit_note(original_invoice):
            raise InvoiceWorkflowError(
                f"Cannot create credit note for invoice with status '{original_invoice.status}'"
            )

        from .service import InvoiceService, resync_invoiced_quantities_for_invoice

        # Create credit note in draft status WITHOUT assigning number
        # Number will be assigned when the credit note is issued via issue_invoice()
        # The series_id can be pre-selected but number is generated on issue
        credit_note = Invoice(
            clinic_id=original_invoice.clinic_id,
            patient_id=original_invoice.patient_id,
            invoice_number=None,  # Assigned when issued
            series_id=series_id,  # Can be pre-selected, defaults to credit_note series on issue
            sequential_number=None,  # Assigned when issued
            credit_note_for_id=original_invoice.id,
            status="draft",
            payment_term_days=0,
            billing_name=original_invoice.billing_name,
            billing_tax_id=original_invoice.billing_tax_id,
            billing_address=original_invoice.billing_address,
            billing_email=original_invoice.billing_email,
            internal_notes=f"Nota de crédito por: {reason}",
            public_notes=f"Rectificación de factura {original_invoice.invoice_number}",
            created_by=created_by,
        )
        db.add(credit_note)
        await db.flush()

        # Create credit note items (negative amounts)
        if items:
            # Partial credit note: only specified items
            for item_spec in items:
                original_item = next(
                    (i for i in original_invoice.items if i.id == item_spec["invoice_item_id"]),
                    None,
                )
                if not original_item:
                    raise InvoiceWorkflowError(
                        f"Item {item_spec['invoice_item_id']} not found in original invoice"
                    )

                quantity = item_spec.get("quantity") or original_item.quantity
                if quantity > original_item.quantity:
                    raise InvoiceWorkflowError(
                        f"Credit note quantity ({quantity}) exceeds original ({original_item.quantity})"
                    )

                credit_item = InvoiceItem(
                    clinic_id=original_invoice.clinic_id,
                    invoice_id=credit_note.id,
                    budget_item_id=original_item.budget_item_id,
                    catalog_item_id=original_item.catalog_item_id,
                    description=original_item.description,
                    internal_code=original_item.internal_code,
                    unit_price=-original_item.unit_price,  # Negative
                    quantity=quantity,
                    discount_type=original_item.discount_type,
                    discount_value=original_item.discount_value,
                    vat_type_id=original_item.vat_type_id,
                    vat_rate=original_item.vat_rate,
                    vat_exempt_reason=original_item.vat_exempt_reason,
                    tooth_number=original_item.tooth_number,
                    surfaces=original_item.surfaces,
                    display_order=original_item.display_order,
                )
                db.add(credit_item)
                await InvoiceService.calculate_item_totals(credit_item)
        else:
            # Full credit note: all items
            for idx, original_item in enumerate(original_invoice.items):
                credit_item = InvoiceItem(
                    clinic_id=original_invoice.clinic_id,
                    invoice_id=credit_note.id,
                    budget_item_id=original_item.budget_item_id,
                    catalog_item_id=original_item.catalog_item_id,
                    description=original_item.description,
                    internal_code=original_item.internal_code,
                    unit_price=-original_item.unit_price,  # Negative
                    quantity=original_item.quantity,
                    discount_type=original_item.discount_type,
                    discount_value=original_item.discount_value,
                    vat_type_id=original_item.vat_type_id,
                    vat_rate=original_item.vat_rate,
                    vat_exempt_reason=original_item.vat_exempt_reason,
                    tooth_number=original_item.tooth_number,
                    surfaces=original_item.surfaces,
                    display_order=idx,
                )
                db.add(credit_item)
                await InvoiceService.calculate_item_totals(credit_item)

        await db.flush()

        # Calculate credit note totals
        await InvoiceService.recalculate_totals(db, credit_note)

        # Add history to credit note
        from .service import InvoiceHistoryService

        await InvoiceHistoryService.add_entry(
            db,
            clinic_id=credit_note.clinic_id,
            invoice_id=credit_note.id,
            action="created",
            changed_by=created_by,
            new_state={
                "status": "draft",
                "credit_note_for": original_invoice.invoice_number,
                "reason": reason,
            },
        )

        await db.flush()
        await resync_invoiced_quantities_for_invoice(db, credit_note)

        return credit_note
