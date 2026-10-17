---
module: gdpr
last_verified_commit: 47a008bcc85677e4e45c93b34d7a7e1525e86f29
---

# gdpr — overview

EU General Data Protection Regulation (2016/679) compliance for a clinic:
data-subject requests (DSR), patient consents, retention policies that gate
erasure, an immutable erasure audit log, and a data-breach register. Delivered
as an optional (`auto_install=False`), removable backend module (issue #44).

## What it is

Admin/triage-authenticated endpoints under `/api/v1/gdpr/` (JWT + RBAC). A
clinic records the rights it must honour (access, rectification, erasure,
portability, restrict), the consents it obtains, the retention rules that
limit erasure, the erasures it actually performs, and the breaches it must
report.

Routes (no `DELETE /requests/{id}` — DSRs are accountability records,
Art. 5(2), immutable except for status transitions):
- `GET /api/v1/gdpr/requests` — list DSRs (filter by status/type)
- `GET /api/v1/gdpr/requests/{id}` — get one DSR
- `POST /api/v1/gdpr/requests` — create a DSR (201)
- `PATCH /api/v1/gdpr/requests/{id}` — transition DSR status
- `GET /api/v1/gdpr/consents` — list consents (per patient)
- `POST /api/v1/gdpr/consents` — record consent grant/withdrawal (201)
- `GET /api/v1/gdpr/consents/current` — latest consent for one (patient, purpose)
- `GET /api/v1/gdpr/retention` — list active retention policies
- `POST /api/v1/gdpr/retention` — create a policy (201)
- `PATCH /api/v1/gdpr/retention/{id}` — update a policy
- `DELETE /api/v1/gdpr/retention/{id}` — delete a policy (204)
- `POST /api/v1/gdpr/erasure` — run a partial erasure (201). The result
  carries a per-scope coverage list (`ErasureCoverage`, see below), so a
  completed run never reads as full DSR coverage (#546).
- `GET /api/v1/gdpr/audit` — list erasure audit logs
- `GET /api/v1/gdpr/breaches` — list breaches
- `GET /api/v1/gdpr/breaches/{id}` — get one breach
- `POST /api/v1/gdpr/breaches` — report a breach (201)
- `PATCH /api/v1/gdpr/breaches/{id}` — update breach status
- `GET /api/v1/gdpr/export/{patient_id}` — portability export (Art. 20)

## Data model

Five tables, all `clinic_id`-scoped and indexed on `clinic_id`:

| Table | Purpose | Art. |
|---|---|---|
| `gdpr_requests` | data-subject requests with a 30-day SLA (v1 ticket tracker: access/erasure/portability tracked; rectification/restrict tracked but do not mutate the patient record; no objection type yet) | 15-20 |
| `patient_consents` | append-only per-event consent trail; latest row per (patient, purpose) is current | 7-8 |
| `retention_policies` | per-clinic retention rules gating erasure | 5(1)(e) |
| `gdpr_erasure_audit_logs` | immutable partial-erasure accountability | 17 |
| `data_breaches` | reportable breach register | 33-34 |

Migration `gdpr_0001_initial` on own Alembic branch (`gdpr`), depending on
`patients@pat_0003` (the patient FK). Followed by `gdpr_0002_single_active_policy`,
`gdpr_0003_subject_notification` (Art. 34 columns) and
`gdpr_0004_canonical_consent_purpose` (backfills pre-canonical purposes).

## Service layer

- `GdprService` — DSR lifecycle (`create_request`, `get_request`,
  `list_requests`, `update_request`); `SlaCalculator` sets
  a 30-day `deadline_at`.
- `ConsentService` — `grant_or_withdraw` APPENDS one row per event
  (grant → withdraw → grant = three rows); `list_consents` returns
  newest-first (created_at + id tiebreak), so the first row per
  (patient, purpose) is current; `current` returns just that row.
  Purposes are stored canonical (`strip().lower()`), so "SMS" and
  "sms " are one purpose, not two; `gdpr_0004` backfills the rows written
  before that rule. A grant requires the shown text
  (`provided_text`); withdrawals carry none. Recording a withdrawal
  publishes `gdpr.consent.withdrawn`, but send paths gate on the
  independent `do_not_contact` field — the record does not itself
  stop sends. Wiring withdrawal into the send path is a parked
  product decision (#562 CONS-02); until it lands, this document is
  the disclosure.
- `RetentionService` — active policies that gate erasure. At most
  one active policy per (clinic, category) (partial unique index,
  `gdpr_0002`); creating one supersedes its predecessors, which stay
  as history. Deactivation is terminal by design: to change a policy,
  create a new one — there is no reactivate path (#562 RET-02).
- `ErasureService` — `erasure_eligible` splits requested categories into
  erasable (policy expired) vs retained (still under hold); `execute` blanks
  identity PII and writes the audit log; `list_audit`.
- `DataBreachService` — breach create/list/update. Art. 33 authority
  notification (`notified_authority_at`) is stamped by the transition into
  `reported`; the Art. 34 subject-notification record
  (`notified_subjects_at` / `notified_subjects_count`, `gdpr_0003`) is set
  explicitly, with no auto-stamp rule - whether notifying people is automatic
  is a parked product decision (#562 SEC-02). Status moves follow
  `_BREACH_TRANSITIONS`: `under_review` to `reported` or `not_reportable`,
  `reported` to `resolved` or `not_reportable`, `not_reportable` back to
  `under_review` to retry. The `reported -> not_reportable` edge covers an
  authority ruling the report below the threshold after notification; the
  latches stay set, because the notification happened.
- `ExportService` — machine-readable portability snapshot.

## Erasure semantics

`ErasureService.execute` never hard-deletes a patient, and returns `None`
(404 upstream) for unknown or other-clinic patient ids — the audit table
FKs `patient_id`, so nothing is written before the lookup. Only the closed
vocabulary `email | phone | identity` (`schemas.ErasureCategory`, 422 on
anything else) can be erased, because only those map onto patient PII
fields (`email`, `billing_email`, `phone`, `national_id`). A mapped
category is erased only when its active retention policy's legal hold has
passed AND its age window has passed: `retention_years == 0` means no age
hold, otherwise the window runs that many years from the patient's
`updated_at` (minimum-honest anchor). Categories with no policy, or with
no field mapping (e.g. `clinical`, `billing`, `radiology` policies document
the hold and always retain), stay retained. Every run writes an
`ErasureAuditLog`, pulls every registered erasure contributor inside the
transaction, and returns a per-scope `coverage` report so a completed
DSR never reads as full coverage (#546). `gdpr.erasure.executed` publishes
after commit as an announcement only.

### Cross-module coverage (#546, ADR 0038)

Erasure pulls a contributor registry, not a fan-out. Each active module
may expose `get_erasure_contributors()`; the loader collects them into
the core `SubjectErasureRegistry`, and `gdpr` calls every contributor
inside the erasure transaction — each redacts its own copies and reports
its own `ErasureCoverage`. A scope with no registered contributor
produces no row, so an uninstalled module is never reported as erased.
A raising contributor rolls the whole run back. The result carries one
row per scope with a `status` of `erased`, `retained` (legal basis, Art.
17(3)) or `not_applicable`:

| Scope | What it covers | Typical status |
|-------|----------------|----------------|
| `patient_record` | identity/contact fields on the patient row | `erased` when any category was erasable |
| `notifications` | recipient/subject/body/context/failure text on the communication log (contributor) | `erased` when a contact category was erasable |
| `recalls` | contact-attempt notes (contributor) | `erased` when a contact category was erasable |
| `patient_timeline` | append-only activity feed (contributor) | `retained` (Art. 17(3)(b)) |
| `budget` | signer email on signed quotes (contributor) | `retained` (Art. 17(3)(e)); `not_applicable` unless `email` is in the run |
| `billing` | issued-invoice fiscal snapshot (contributor) | `retained` (Art. 17(3)(b)); `not_applicable` unless `email`/`identity` is in the run |
| `clinical_notes` | clinical note text (contributor) | `retained` (Art. 17(3)(c)/(h)) |
| `documents` | generated prescriptions/certificates/referrals (contributor) | `retained` (Art. 17(3)(c)/(h)) |
| `media` | imaging, clinical photos, uploaded files (contributor) | `retained` (Art. 17(3)(c)/(h)) |

Every row above is now a module-owned contributor (#657) — `gdpr`
hardcodes none of them. The last three replaced a single `clinical` row:
there is no `clinical` module, so the three modules that actually hold the
data own one scope each, and uninstalling `documents` removes its row
instead of leaving `gdpr` claiming coverage for a module that is gone.
Retention-only scopes extend `RetainedScopeContributor` and declare the
erasure categories they hold a copy of, so a run that touches none of them
reports `not_applicable` rather than claiming to retain data it never
looked at.

## Agent tools

Eight tools: `create_gdpr_request`, `list_gdpr_requests`, `record_gdpr_consent`,
`list_gdpr_consents`, `create_retention_policy`, `execute_partial_erasure`,
`report_breach`, `list_breaches`.
Each wraps the matching service method, filters by `ctx.clinic_id`, and
returns native values (UUID/datetime coerced at the registry).

## Tenancy

Every query filters by `clinic_id`; a request/export/erasure for another
clinic's patient 404s rather than 403s, matching repo convention.

## v1 scope (part of #44, not the whole of it)

- No frontend layer: staff reach this through the copilot tools or raw HTTP.
- Export covers identity + consents + DSRs only — not clinical,
  appointments, or billing.
- No retention-expiry flagging job and no export access log yet; both stay
  tracked in #44 alongside the UI.

## Constraints

Own Alembic branch (`gdpr`), depending on `patients@pat_0003` — the only
cross-module FK is the `patients.id` reference. `manifest.depends = ["patients"]`.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.