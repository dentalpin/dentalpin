# Changelog — budget module

## Unreleased

- feat(#287): `send_method` accepts `whatsapp` (router/workflow/tools; legacy `send_email` kept); the send modal offers a button per configured manual channel; the public-link wa.me button is secondary ('Open in WhatsApp'); the reminder cron's clinics query no longer references the never-created `clinics.deleted_at` column (it raised on every tick).

- fix(#101): a failed signature fetch no longer renders as 'not signed' — fetchSignature only nulls on a real 404 and the card shows an error state with Retry.

- feat(#207): the in-clinic accept/reject signature modal prefills "Signed by" with the patient's name and email while the relation is *patient*; changing the relation clears it.

- fix(#203): the back link on budget detail/new rendered the raw key `actions.back` when arriving from the patient page — the key never existed in any locale; use `common.back` ("Volver").

- fix(#181): `_recalculate_totals` prorates the global discount per line (`pricing.allocate_global_discount`) and charges VAT on the discounted base, so the quote's `total_discount`/`total_tax` match the invoice built from it (`total` unchanged). New `pricing.net_line_total` + `items[].net_line_total` on the detail response; quote detail, public page and PDF show the net price with the gross struck through and the global share labelled.
- fix(#176): adding/removing lines on a quote linked to a treatment plan is refused (409 `PlanOwnsLinesError`); lines are managed from the plan. The detail page hides the add/remove actions and points at the plan.
- feat(#177): new `budget.new.form` slot on `/budgets/new` (`ctx = { patient }`).
- refactor: `service.lookup_linked_plan` is the single raw-SQL plan reverse-lookup (was duplicated in `workflow.py` and the detail endpoint).
- fix(#184): type-check clean — item helpers on the detail page accept the readonly item view.
- feat(#184): `BudgetListResponse` exposes `plan_number_snapshot` so patient-side lists can show the plan link without importing treatment_plan.
- fix(#183): the three plan-sync handlers are transactional (ADR 0019); a failed mirror now fails the request instead of leaving the quote out of sync with the plan.
- fix(#183): `budget.superseded` is published before commit like every other event — the treatment_plan handler shares the session, so the FK to the new budget row resolves. Removes the documented "sole deviation from the publish-before-commit pattern".
- chore: drop `BudgetService.on_treatment_performed`, a no-op placeholder subscribed to `odontogram.treatment.performed`.
- feat(events): `budget.accepted` payload now carries `items[]` with a
  per-line ex-tax `net_amount` (line discount + prorated global
  discount) so `treatment_plan` can reprice sessions from the snapshot
  (issue #167). New `pricing.allocate_global_discount` /
  `net_line_amount` are the single proration formula; `BudgetDetailResponse`
  exposes `items[].global_discount_share` for the invoice wizard.

- fix(items): `PUT /budgets/{id}/items/{item_id}` now honours an explicit
  `null` on nullable fields (`discount_type`, `discount_value`,
  `tooth_number`, `surfaces`, `notes`) — clearing a line discount was
  silently ignored and totals stayed wrong. `null` on NOT NULL fields is
  still ignored.

- fix(workflow): plan ↔ budget lifecycle desync (issue #162).
  `cancel_budget` now publishes `budget.cancelled` (with `plan_id`) so a
  directly-cancelled quote reopens its pending plan instead of leaving it
  stranded; `POST /budgets/{id}/resend` now publishes `budget.superseded`
  (after commit — see gotcha in CLAUDE.md) so the plan's `budget_id`
  follows the new version, refreshes `plan_status_snapshot` from the live
  plan, and rejects non-terminal budgets with 400. The
  `create_from_plan_snapshot` idempotency check now treats rejected and
  expired budgets as terminal (not just cancelled), so re-confirming a
  reactivated plan produces a fresh quote.

- feat(ui): "Resend" button on the budget detail page — clones a
  rejected/expired/cancelled budget to a new draft version and navigates
  to it. Removed the orphan `RenegotiateBudgetModal.vue` (never imported).

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast, across the
  detail page, the item modal, the new-budget page and the list (delete,
  PDF). `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Reported by users who saw
  *Error* on *Mark as sent* / *Send email* / *Accept quote* when the real
  cause was an empty budget or a patient without email. `downloadPDFAt`
  also stops throwing a hardcoded English string and reads the response
  body instead.

- refactor(scheduler): declare the budget cron jobs (`expire_budgets`,
  `send_budget_reminders`, `purge_budget_access_logs`) via
  `get_scheduled_jobs()` instead of being imported by name in
  `app/core/scheduler.py`.

- feat(agents): expose `tools.py` for the copilot agentic layer —
  `list_budgets`, `get_budget` (READ), `send_budget` (DESTRUCTIVE; emails
  the patient). Thin wrappers over `BudgetService`/`BudgetWorkflowService`;
  clinic-scoped; RBAC via existing `budget.read`/`budget.write`.

- feat(service): ``create_budget`` now accepts an optional pre-set
  ``budget_number`` in the ``data`` dict; absent/``None`` falls back
  to ``BudgetNumberService.generate_number`` as before. Used by the
  migration importer to preserve historic Gesdén ``Presu.NumPresu``
  values instead of renumbering decades-old presupuestos into the
  current year.
- refactor(useBudgets): dedup the ``toListItem`` builder (2 sites → 1 helper).
- refactor(types): drop the ``as unknown as Record<string, unknown>`` cast pattern (8 sites) now that ``useApi`` accepts ``object`` payloads.
- refactor(perms): migrate hardcoded ``can('budget.{write,admin}')`` strings on the budget list and detail pages to ``PERMISSIONS.budget.*``.
- perf(cron): ``expire_budgets`` and ``send_budget_reminders`` now
  process clinics concurrently behind an ``asyncio.Semaphore(5)``
  instead of serially. A slow clinic no longer delays the rest of
  the cycle, so a heavy multi-clinic install keeps hitting its
  scheduled windows.
- chore(events): all publishers in this module now ``await
  event_bus.publish(...)`` — bus is async-first as of core sprint 3.
- perf(budgets-list): switch to direct ``COUNT(Budget.id)`` over the
  shared filter set; the previous ``select_from(query.subquery())``
  pattern materialised joined patient/creator data just to count.
- perf(pdf): ``BudgetPDFService.generate_pdf`` is now ``async`` and
  offloads the WeasyPrint render to ``asyncio.to_thread`` so the
  event loop keeps serving other requests while a budget PDF
  renders. All call sites updated.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).

### Added (lists redesign, 2026-05-14)

- `GET /api/v1/budget/budgets` accepts new params: `budget_ids[]`,
  `assigned_professional_id`, `valid_until_before`, `valid_until_after`,
  `sort=field:dir` (whitelist: `created_at`, `valid_until`, `total`,
  `status`, `budget_number`).
- New slots exposed on the /budgets list page: `budget.list.filter`
  (toolbar) and `budget.list.row.payments` (per-row cell). Payments
  module registers fillers for the "Cobro" multi-select chip and
  the collected/pending mini-progress bar — no cross-module imports.
- List page rewritten on `DataListLayout` + `FilterBar` +
  `useListQuery`. Card view <md, URL-synced filters, sort dropdown,
  filters for status, professional autocomplete, validity preset,
  date range, and payment status (cross-module via slot).

- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

### Added (signed PDF, 2026-04-28)

- Signed-PDF generation: ``BudgetPDFService.generate_pdf`` now
  accepts an optional ``BudgetSignature``. When provided, the PDF
  embeds the captured PNG plus an audit footer (signed_by,
  signed_at, signature_method, document_hash).
- ``BudgetWorkflowService.accept_budget`` renders the signed PDF
  immediately after creating the signature and persists the SHA-
  256 of those bytes on ``BudgetSignature.document_hash`` —
  tamper detection for any future re-render.
- Staff endpoints:
  - ``GET /api/v1/budget/budgets/{id}/pdf/signed`` — 404 when no
    signature exists, otherwise the signed PDF (``Cache-Control:
    private, no-store``).
  - ``GET /api/v1/budget/budgets/{id}/signature`` — signature
    metadata (no raw PNG payload) via the new
    ``SignatureMetaResponse`` schema.
- Public endpoint:
  - ``GET /api/v1/budget/public/budgets/{token}/pdf/signed`` —
    cookie-protected (same per-token JWT cookie as the rest of
    the public flow), 404 when not yet accepted, rate-limited to
    10/minute per token, audit row appended to
    ``BudgetAccessLog`` with ``method_attempted=
    "download_signed_pdf"`` and ``success=True`` (so it never
    contributes to the lockout counter).
- Frontend:
  - Staff: new ``BudgetSignatureCard.vue`` mounted on the budget
    detail page when ``status ∈ {accepted, completed}``. Shows
    signed_by / signed_at / method / relationship / hash and a
    "Download signed PDF" button. Backed by
    ``useBudgets().fetchSignature`` + ``downloadSignedPDF``.
  - Public: download button on the ``already_accepted`` state of
    ``/p/budget/<token>``. On 401 (cookie expired) the page
    shows the verify form again and retries the download once
    the patient re-verifies.
- i18n: ``budget.signature.{signedAt, methodLabel,
  relationshipLabel, documentHash, hashHint, downloadSignedPdf,
  downloadError, notSigned, method.{drawn,clickAccept,external}}``
  and ``budget.public.download.{signedPdf, notSigned, error,
  reauthIntro}`` in ES + EN.

### Removed (2026-04-29)

- ``BudgetWorkflowService.complete_budget`` + ``POST /budgets/{id}/complete``
  endpoint + the "Marcar completado" button. The transition
  ``accepted → completed`` was a bookkeeping flag with no auto-
  trigger and no real consumer (the documented ``budget.completed``
  event was never actually published). Use invoice paid / fully
  invoiced as the financial-closure signal instead. The
  ``InvoiceService.on_budget_completed`` handler in billing is
  also removed.
- Frontend: ``completeBudget`` action and ``canComplete`` helper
  in ``useBudgets``; the ``budget.actions.complete`` and
  ``budget.messages.completed`` i18n keys.

### Added (patient view, 2026-04-29 — PR3)

- Patient-facing public budget view at ``/p/budget/<token>``
  (frontend route allowlisted in ``auth.global.ts``).
- New ``public`` Nuxt layout — clinic header, mobile-first content,
  no app sidebar.
- ``usePublicBudget`` composable wrapping the six public endpoints
  with ``credentials: 'include'`` so the HttpOnly cookie session
  flows through.
- ``BudgetVerifyForm`` component renders the right input per
  ``meta.method`` (phone_last4 / dob / manual_code) and surfaces
  the error states (invalid, locked, rate_limited, expired).
- Page state machine: cold (locked / expired / already-decided) →
  verify form → budget detail with three CTAs (accept with
  optional signature, reject with reason, "I have questions" /
  request changes).
- i18n strings for the whole patient flow under
  ``budget.public.*`` in ES + EN.

### Added (frontend, 2026-04-29 — PR2)

- Workflow modals (`components/clinical/modals/`):
  `RenegotiateBudgetModal`, `AcceptInClinicModal`,
  `SetPublicCodeModal`. The accept-in-clinic modal includes an
  optional canvas signature pad (PNG-encoded).
- Settings area `/settings/budgets/{,expiry,reminders,public-link}`
  with a new `useBudgetSettings` composable wired to
  `GET / PATCH /api/v1/auth/clinic/settings/budget` (admin-only).
- New i18n strings for the budget workflow + settings copy.

### Added (plan/budget workflow rework, 2026-04-29 — PR1)

- Acceptance / rejection metadata: `accepted_via`, `rejection_reason`,
  `rejection_note` columns. `accept_budget` accepts an
  `accepted_via` argument (`remote_link` / `in_clinic` / `manual`).
- Public-link 2-factor auth (ADR 0006): new columns `public_token`
  (UUID, unique), `public_auth_method`, `public_auth_secret_hash`,
  `public_locked_at`, `viewed_at`, `last_reminder_sent_at`.
- New table `budget_access_logs` for verification audit + rate
  limit + lockout.
- Plan denormalization columns `plan_number_snapshot` /
  `plan_status_snapshot` so endpoints in this module render plan
  context without importing `treatment_plan` ORM models.
- Workflow methods: `cancel_for_renegotiation`, `mark_viewed`,
  `send_reminder`, `set_public_code`, `unlock_public`,
  `clone_to_new_draft`, `resolve_public_auth_method`,
  `verify_public_access`. `BudgetService.create_from_plan_snapshot`
  builds the draft budget when a plan is confirmed (idempotent).
- Six public endpoints under `/api/v1/public/budgets/{token}/`:
  `meta`, `verify`, `GET /`, `accept`, `reject`, `request-changes`.
  Cookie session (HS256, scoped to token, TTL 30min) signed with
  `BUDGET_PUBLIC_SECRET_KEY`.
- Six authenticated endpoints: `renegotiate`, `accept-in-clinic`,
  `resend`, `send-reminder`, `set-public-code`, `unlock-public`.
- Granular permissions `budget.{renegotiate,accept_in_clinic}`.
- New events with snapshot payloads: `budget.expired`,
  `budget.renegotiated`, `budget.viewed`, `budget.reminder_sent`.
  `budget.rejected` now also published with snapshot.
- Cron jobs (`backend/app/modules/budget/tasks.py`):
  `expire_budgets` (daily 02:00), `send_budget_reminders` (daily
  09:00), `purge_budget_access_logs` (daily 04:00, 90-day retention).
- `manifest.depends` now declares `odontogram` to match the existing
  `budget_items.treatment_id` FK.

### Refactored — module isolation (ADR 0003)

- Removed cross-module ORM imports from event handlers
  (`__init__.py`) and `router.py`. Snapshot-based event payloads
  carry the data needed; the budget detail endpoint reads the
  linked plan via raw SQL.
- `budget` no longer imports `app.modules.treatment_plan` or
  `app.modules.odontogram` at runtime.

## 0.1.0 — initial

- Budget creation + versioning + signature workflow.
- PDF generation.
- Events emitted: `budget.sent`, `budget.accepted`.
- Bidirectional sync with `treatment_plan` via events.
