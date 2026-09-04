---
module: gdpr
last_verified_commit: 8b8e9375
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
- `GET /api/v1/gdpr/retention` — list active retention policies
- `POST /api/v1/gdpr/retention` — create a policy (201)
- `PATCH /api/v1/gdpr/retention/{id}` — update a policy
- `DELETE /api/v1/gdpr/retention/{id}` — delete a policy (204)
- `POST /api/v1/gdpr/erasure` — run a partial erasure (201)
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
`patients@pat_0003` (the patient FK).

## Service layer

- `GdprService` — DSR lifecycle (`create_request`, `get_request`,
  `list_requests`, `update_request`); `SlaCalculator` sets
  a 30-day `deadline_at`.
- `ConsentService` — `grant_or_withdraw` APPENDS one row per event
  (grant → withdraw → grant = three rows); `list_consents` returns
  newest-first, so the first row per (patient, purpose) is current.
- `RetentionService` — active policies that gate erasure.
- `ErasureService` — `erasure_eligible` splits requested categories into
  erasable (policy expired) vs retained (still under hold); `execute` blanks
  identity PII and writes the audit log; `list_audit`.
- `DataBreachService` — breach create/list/update.
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
`ErasureAuditLog` and publishes `gdpr.erasure.executed`.

## Agent tools

Six tools: `create_gdpr_request`, `list_gdpr_requests`, `record_gdpr_consent`,
`list_gdpr_consents`, `create_retention_policy`, `execute_partial_erasure`.
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