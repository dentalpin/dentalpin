"""Event type constants for the event bus."""


class EventType:
    """Constants for event types used across modules.

    Naming convention: {entity}.{action}
    """

    # Tenant lifecycle (multi-tenancy Fase 1 — declared; first publisher
    # arrives in Fase 2a when the resolver is wired into `get_db`).
    TENANT_RESOLVED = "tenant.resolved"

    # Clinic lifecycle. Published by ``POST /auth/setup`` after the clinic,
    # its admin and the membership are committed. Payload: (clinic_id,
    # country, currency, timezone, language, vat_preset, created_by,
    # source). Modules react by seeding their defaults (catalog, billing
    # series, cabinet, hours) — handlers must be idempotent and open their
    # own DB session (this is the one event published *after* the
    # publisher commits, so there is nothing uncommitted to miss).
    CLINIC_CREATED = "clinic.created"

    # Patient events
    PATIENT_CREATED = "patient.created"
    PATIENT_UPDATED = "patient.updated"
    PATIENT_ARCHIVED = "patient.archived"
    PATIENT_MEDICAL_UPDATED = "patient.medical_updated"

    # Appointment events
    APPOINTMENT_SCHEDULED = "appointment.scheduled"
    APPOINTMENT_UPDATED = "appointment.updated"
    APPOINTMENT_COMPLETED = "appointment.completed"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_NO_SHOW = "appointment.no_show"
    # Generic status transition event — always published by
    # ``AppointmentService.transition`` alongside the specific ones above.
    # Payload carries from_status / to_status / changed_at / changed_by so
    # subscribers can subscribe once and react to any transition without
    # knowing the state machine.
    APPOINTMENT_STATUS_CHANGED = "appointment.status_changed"
    APPOINTMENT_CONFIRMED = "appointment.confirmed"
    APPOINTMENT_CHECKED_IN = "appointment.checked_in"
    APPOINTMENT_IN_TREATMENT = "appointment.in_treatment"
    # Cabinet (re)assignment — published by AppointmentService.assign_cabinet.
    # Consumers that care about where a patient physically is (real-time
    # kanban, occupancy dashboards) subscribe to this event. The payload
    # carries from_cabinet_id / to_cabinet_id / changed_at / changed_by;
    # either cabinet id can be null (first assignment or an unassign).
    APPOINTMENT_CABINET_CHANGED = "appointment.cabinet_changed"

    # Treatment events (for future use)
    TREATMENT_COMPLETED = "treatment.completed"

    # Budget events
    BUDGET_CREATED = "budget.created"
    BUDGET_SENT = "budget.sent"
    BUDGET_ACCEPTED = "budget.accepted"
    BUDGET_REJECTED = "budget.rejected"
    # Auto-expired by the daily cron when ``valid_until < today`` and the
    # budget was still ``sent`` or ``draft``. Payload carries a snapshot
    # (budget_id, plan_id, patient_id, days_overdue) so subscribers do not
    # need to import budget models.
    BUDGET_EXPIRED = "budget.expired"
    # Reception cancelled a sent budget for renegotiation. The companion
    # plan is unlocked back to ``draft``. Payload carries
    # (budget_id, plan_id, patient_id, version, cancelled_at).
    BUDGET_RENEGOTIATED = "budget.renegotiated"
    # Staff cancelled a budget directly (POST /budgets/{id}/cancel). The
    # companion pending plan reopens to ``draft``. Payload carries
    # (clinic_id, budget_id, patient_id, budget_number, plan_id, reason,
    # cancelled_by, occurred_at). NOT published when the cancellation is
    # initiated by ``treatment_plan.reopen()`` — the plan module already
    # owns that transition (``publish_event=False``); an echo here would
    # send the plan through a reopen it is already performing.
    BUDGET_CANCELLED = "budget.cancelled"
    # A terminal budget (rejected/expired/cancelled) was cloned to a new
    # draft version ("Resend"). The plan's ``budget_id`` link must follow
    # the new version; plan status is untouched. Published before commit
    # like everything else: the treatment_plan handler is transactional
    # (ADR 0019) so the new row is visible to it. Payload carries
    # (clinic_id, budget_id [old], new_budget_id, patient_id, plan_id,
    # version [new], resent_by, occurred_at).
    BUDGET_SUPERSEDED = "budget.superseded"
    # Patient opened the public link (first time). Payload carries
    # (budget_id, plan_id, patient_id, viewed_at, ip_hash). Idempotent.
    BUDGET_VIEWED = "budget.viewed"
    # Automatic reminder dispatched to the patient (7d / 14d milestone).
    # Payload carries (budget_id, plan_id, patient_id, milestone_days,
    # sent_at). Only fired when ``budget_reminders_enabled`` for the clinic.
    BUDGET_REMINDER_SENT = "budget.reminder_sent"

    # Email events (legacy — kept for one release; see NOTIFICATION_* below).
    # The notifications gateway dual-publishes these for channel=="email" so
    # patient_timeline keeps working until it migrates to the generic events.
    EMAIL_SENT = "email.sent"
    EMAIL_FAILED = "email.failed"

    # Notification (multi-channel) lifecycle events — published by the
    # notifications gateway across every channel (email, whatsapp, …).
    NOTIFICATION_QUEUED = "notification.queued"
    NOTIFICATION_SENT = "notification.sent"
    NOTIFICATION_FAILED = "notification.failed"
    NOTIFICATION_DELIVERED = "notification.delivered"
    NOTIFICATION_REPLY_RECEIVED = "notification.reply_received"

    # Invoice events
    INVOICE_CREATED = "invoice.created"
    INVOICE_ISSUED = "invoice.issued"
    INVOICE_SENT = "invoice.sent"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PARTIAL_PAID = "invoice.partial_paid"
    INVOICE_CANCELLED = "invoice.cancelled"
    INVOICE_VOIDED = "invoice.voided"

    # Payment events
    PAYMENT_RECORDED = "payment.recorded"
    # Published whenever an allocation is created or moved (initial create
    # of a Payment, reallocation across budget/on_account/invoice link).
    # Payload carries (clinic_id, payment_id, target_type, target_id,
    # amount, previous_target_type, previous_target_id) — previous_* are
    # null on initial creation.
    PAYMENT_ALLOCATED = "payment.allocated"
    # Published when a Refund row is created (partial or full reversal of
    # a Payment). Payload: (clinic_id, payment_id, refund_id, amount,
    # reason_code). Replaces the legacy `is_voided` flag — a total reverso
    # is just Refund(amount=Payment.amount).
    PAYMENT_REFUNDED = "payment.refunded"
    PAYMENT_VOIDED = "payment.voided"

    # Credit note events
    CREDIT_NOTE_ISSUED = "credit_note.issued"

    # Odontogram events
    ODONTOGRAM_SURFACE_UPDATED = "odontogram.surface.updated"
    ODONTOGRAM_TOOTH_UPDATED = "odontogram.tooth.updated"
    ODONTOGRAM_CONDITION_CHANGED = "odontogram.condition.changed"

    # Tooth treatment events (for budget module integration)
    ODONTOGRAM_TREATMENT_ADDED = "odontogram.treatment.added"
    ODONTOGRAM_TREATMENT_STATUS_CHANGED = "odontogram.treatment.status_changed"
    ODONTOGRAM_TREATMENT_PERFORMED = "odontogram.treatment.performed"
    ODONTOGRAM_TREATMENT_DELETED = "odontogram.treatment.deleted"

    # Document / media events
    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_DELETED = "document.deleted"
    DOCUMENT_ARCHIVED = "document.archived"
    # Published by the documents module after a prescription, certificate,
    # referral or radiology request is rendered as PDF. Payload carries
    # (document_id, clinic_id, patient_id, document_type, title, created_by?).
    # Consumed by activity_journal for timeline entries.
    DOCUMENT_GENERATED = "document.generated"
    # Photo-aware subset of DOCUMENT_UPLOADED. Fired alongside the
    # generic event whenever ``media_kind ∈ {photo, xray}`` so timeline
    # / gallery subscribers can render thumbnails inline without
    # filtering every document upload by mime_type.
    PHOTO_UPLOADED = "media.photo_uploaded"
    # Polymorphic attachment lifecycle. Subscribers (e.g. patient_timeline)
    # can react to documents being attached to plans, notes, visits, etc.
    ATTACHMENT_LINKED = "media.attachment_linked"
    ATTACHMENT_UNLINKED = "media.attachment_unlinked"
    # Before/after pairing. PAIR_CREATED carries both document ids so the
    # timeline can render the comparison inline.
    PAIR_CREATED = "media.pair_created"
    PAIR_REMOVED = "media.pair_removed"

    # Treatment plan events
    TREATMENT_PLAN_CREATED = "treatment_plan.created"
    TREATMENT_PLAN_STATUS_CHANGED = "treatment_plan.status_changed"
    TREATMENT_PLAN_TREATMENT_ADDED = "treatment_plan.treatment_added"
    TREATMENT_PLAN_TREATMENT_REMOVED = "treatment_plan.treatment_removed"
    TREATMENT_PLAN_TREATMENT_COMPLETED = "treatment_plan.treatment_completed"
    TREATMENT_PLAN_BUDGET_SYNC_REQUESTED = "treatment_plan.budget_sync_requested"
    # Doctor closed the plan clinically (``draft`` → ``pending``). Payload
    # carries a full snapshot so subscribers (budget for draft creation,
    # patient_timeline for audit) do not need to import treatment_plan
    # models. Snapshot fields: plan_id, plan_number, clinic_id, patient_id,
    # patient_full_name, items[{id, catalog_item_id, tooth, surfaces,
    # quantity, estimated_price}], total_estimated, confirmed_at,
    # confirmed_by_user_id.
    TREATMENT_PLAN_ITEMS_REORDERED = "treatment_plan.items_reordered"
    TREATMENT_PLAN_CONFIRMED = "treatment_plan.confirmed"
    # Plan transitioned to terminal ``closed`` state. Payload:
    # (plan_id, clinic_id, patient_id, closure_reason, closure_note,
    # closed_at, closed_by_user_id, previous_status).
    TREATMENT_PLAN_CLOSED = "treatment_plan.closed"
    # Plan revived from ``closed`` back to ``draft``. Payload:
    # (plan_id, clinic_id, patient_id, previous_closure_reason,
    # reactivated_at, reactivated_by_user_id).
    TREATMENT_PLAN_REACTIVATED = "treatment_plan.reactivated"

    # Treatment-plan completion audit (kept here — emitted by treatment_plan
    # when an item is completed without a clinical note, consumed by
    # patient_timeline for compliance audit).
    TREATMENT_PLAN_ITEM_COMPLETED_WITHOUT_NOTE = "treatment_plan.item_completed_without_note"
    # Per-session completion of a multi-step plan item. Payload:
    # (plan_id, item_id, session_id, sequence, label, amount,
    # treatment_id, patient_id, clinic_id, completed_by, occurred_at).
    # Subscribers: payments (earned ledger upsert keyed on
    # (treatment_id, session_id)). Single-session items still publish
    # this once on completion; payments stops listening to the legacy
    # TREATMENT_PLAN_TREATMENT_COMPLETED earned path.
    TREATMENT_PLAN_ITEM_SESSION_COMPLETED = "treatment_plan.item_session_completed"

    # Clinical-notes events (clinical_notes module — replaces the legacy
    # ``treatment_plan.{plan,item}_note_created`` pair).
    CLINICAL_NOTE_ADMINISTRATIVE_CREATED = "clinical_notes.administrative_created"
    CLINICAL_NOTE_DIAGNOSIS_CREATED = "clinical_notes.diagnosis_created"
    CLINICAL_NOTE_TREATMENT_CREATED = "clinical_notes.treatment_created"
    CLINICAL_NOTE_PLAN_CREATED = "clinical_notes.plan_created"
    # Appointment-owner notes. Payload mirrors the other four — patient_id
    # is resolved via the appointment's patient_id so subscribers
    # (patient_timeline) don't need to know about the agenda model.
    CLINICAL_NOTE_APPOINTMENT_CLINICAL_CREATED = "clinical_notes.appointment_clinical_created"
    CLINICAL_NOTE_APPOINTMENT_ADMINISTRATIVE_CREATED = (
        "clinical_notes.appointment_administrative_created"
    )

    # Visit-level note event (agenda module — reuses AppointmentTreatment.notes)
    AGENDA_VISIT_NOTE_UPDATED = "agenda.visit_note_updated"

    # Verifactu compliance events
    VERIFACTU_RECORD_REJECTED = "verifactu.record.rejected"

    # Migration import events (migration_import module — DPMF importer, issue #78)
    # Job lifecycle:
    MIGRATION_JOB_STARTED = "migration.job.started"
    MIGRATION_JOB_COMPLETED = "migration.job.completed"
    MIGRATION_JOB_FAILED = "migration.job.failed"
    # Sync agent uploaded a binary that matched a `_files` staging row.
    # Payload: (job_id, staging_id, document_id).
    MIGRATION_BINARY_RESOLVED = "migration.binary.resolved"
    # Internal progress signal — mapper bumps ImportJob.processed_entities.
    # Payload: (job_id, entity_type, count).
    MIGRATION_ENTITY_PERSISTED = "migration.entity.persisted"

    # Periodontogram events (periodontogram module — SEPA snapshot, issue #79)
    # Fired when a draft snapshot transitions to ``closed``. Payload:
    # (snapshot_id, patient_id, clinic_id, closed_at, closed_by, indices)
    # where ``indices`` is the JSONB blob ``{bop_pct, pi_pct, cal_mean_mm,
    # deep_pockets_count}``. Reserved for patient_timeline integration.
    PERIODONTOGRAM_SNAPSHOT_CLOSED = "periodontogram.snapshot.closed"

    # Recalls events (recalls module — patient call-back workflow, issue #62)
    # Foundation for a future outreach module that will subscribe to react
    # with WhatsApp/SMS/email automation. Recalls itself never sends.
    RECALL_CREATED = "recall.created"
    # Reserved for a future cron tick at month start. Not published in V1.
    RECALL_DUE = "recall.due"
    RECALL_COMPLETED = "recall.completed"
    RECALL_SNOOZED = "recall.snoozed"
    RECALL_CANCELLED = "recall.cancelled"

    # Copilot events (copilot module — conversational agent, issue #81).
    # Tool invocations already land in ``agent_audit_logs``; these surface
    # session lifecycle + budget so analytics/dashboards can subscribe.
    COPILOT_SESSION_STARTED = "copilot.session.started"
    COPILOT_SESSION_ENDED = "copilot.session.ended"
    COPILOT_TOOL_INVOKED = "copilot.tool.invoked"
    COPILOT_BUDGET_THRESHOLD_REACHED = "copilot.budget.threshold_reached"
    COPILOT_DIGEST_SENT = "copilot.digest.sent"

    # Inventory events (inventory module — stock list with low-stock
    # alerts, roadmap #220). INVENTORY_STOCK_LOW fires once per not-low →
    # low crossing (creation at/below threshold counts). Payload:
    # (clinic_id, item_id, name, category, stock_quantity,
    # min_quantity). No bundled subscriber; a future notifications or
    # procurement module may subscribe without importing inventory.
    INVENTORY_STOCK_LOW = "inventory.low_stock"

    # Lab orders events (lab_orders module — external laboratory work,
    # roadmap #221). Fired when PATCH changes an order's status (the same
    # update auto-stamps received_date on ``received``). Payload:
    # (clinic_id, order_id, patient_id, status, work_type,
    # tooth_reference). No bundled subscriber; optional modules
    # (notifications / patient_timeline) may subscribe without importing
    # lab_orders.
    LAB_ORDER_STATUS_CHANGED = "lab_order.status_changed"

    # Staff tasks events (staff_tasks module — staff handoff board,
    # roadmap #219). STAFF_TASK_CREATED fires on creation;
    # STAFF_TASK_STATUS_CHANGED on every status transition (open →
    # claimed → done, or cancelled). Payload: (clinic_id, task_id,
    # status, priority, assignee_id, due_date). No bundled subscriber;
    # future modules (notifications / patient_timeline) may subscribe
    # without importing staff_tasks.
    STAFF_TASK_CREATED = "staff_task.created"
    STAFF_TASK_STATUS_CHANGED = "staff_task.status_changed"

    # Purchase order events (purchase_orders module — procurement execution
    # layer, roadmap #227). PUBLISHED in the same transaction as the change
    # (ADR 0019). No bundled subscriber today; `inventory_reorder` (#227-4)
    # and `supplier_ratings` (#227-5) are expected to subscribe without
    # importing purchase_orders.
    PURCHASE_ORDER_CREATED = "purchase_order.created"
    PURCHASE_ORDER_STATUS_CHANGED = "purchase_order.status_changed"
    PURCHASE_ORDER_RECEIVED = "purchase_order.received"

    # Telephony events (telephony module — CTI screen-pop + call log,
    # issue #64). Fired by the inbound CTI webhook after normalization
    # and caller→patient matching. Payload: (clinic_id, call_log_id,
    # call_id, event, direction, from_number, to_number, patient_id —
    # null when unmatched). CALL_UNKNOWN_CALLER fires alongside
    # CALL_RINGING when no patient matched. No bundled subscriber;
    # optional modules (patient_timeline / integrations) may subscribe
    # without importing telephony.
    CALL_RINGING = "call.ringing"
    CALL_ANSWERED = "call.answered"
    CALL_ENDED = "call.ended"
    CALL_MISSED = "call.missed"
    CALL_UNKNOWN_CALLER = "call.unknown_caller"

    # GDPR compliance events (gdpr module — data-subject rights, issue #44).
    # Published by the gdpr module's services so optional subscribers
    # (patient_timeline / notifications / audit exports) react to rights
    # lifecycle without importing gdpr models.
    # Payload: (clinic_id, request_id, patient_id, request_type).
    GDPR_REQUEST_CREATED = "gdpr.request.created"
    # Payload: (clinic_id, request_id, patient_id, from_status, to_status,
    # changed_by).
    GDPR_REQUEST_STATUS_CHANGED = "gdpr.request.status_changed"
    # Consent grant / withdrawal. Payload:
    # (clinic_id, consent_id, patient_id, purpose).
    GDPR_CONSENT_GRANTED = "gdpr.consent.granted"
    GDPR_CONSENT_WITHDRAWN = "gdpr.consent.withdrawn"
    # Partial erasure executed. Payload: (clinic_id, patient_id, request_id,
    # erased_categories, retained_categories).
    GDPR_ERASURE_EXECUTED = "gdpr.erasure.executed"
    # Breach reported. Payload: (clinic_id, breach_id, affected_people).
    GDPR_BREACH_REPORTED = "gdpr.breach.reported"
