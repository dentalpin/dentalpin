# GDPR module

EU General Data Protection Regulation (2016/679) compliance for a clinic:
data-subject requests (DSR), patient consents, retention policies that gate
erasure, an immutable erasure audit log, and a data-breach register.

## What it does

Routes mounted at `/api/v1/gdpr/`.

- `GET    /requests`          — list DSRs (filter by status/type); `gdpr.requests.read`
- `GET    /requests/{id}`     — single DSR; `gdpr.requests.read`
- `POST   /requests`          — create a DSR (201); `gdpr.requests.write`
- `PATCH  /requests/{id}`     — transition status; auto-stamps `resolved_at`; `gdpr.requests.write`
- (no `DELETE /requests/{id}` — DSRs are accountability records, Art. 5(2),
  immutable except for status transitions)
- `GET    /consents`          — list consents (optionally per patient); `gdpr.consents.read`
- `POST   /consents`          — record a consent grant or withdrawal (201); `gdpr.consents.write`
- `GET    /retention`         — list active retention policies; `gdpr.retention.read`
- `POST   /retention`         — create a policy; `gdpr.retention.write`
- `PATCH  /retention/{id}`    — update a policy; `gdpr.retention.write`
- `DELETE /retention/{id}`    — delete a policy (204); `gdpr.retention.write`
- `POST   /erasure`           — run a partial erasure (Art. 17); `gdpr.requests.write`
- `GET    /audit`             — list erasure audit logs; `gdpr.audit.read`
- `GET    /breaches`          — list breaches; `gdpr.breaches.read`
- `GET    /breaches/{id}`     — single breach; `gdpr.breaches.read`
- `POST   /breaches`          — report a breach; `gdpr.breaches.write`
- `PATCH  /breaches/{id}`     — update breach status; `gdpr.breaches.write`
- `GET    /export/{patient_id}` — portability export (Art. 20); `gdpr.requests.read`

## Data model

5 tables, all `clinic_id`-scoped:

- `gdpr_requests` — a DSR: `requester_name`, `requester_email`,
  `request_type` (access | rectification | erasure | portability | restrict),
  `status` (received | in_progress | completed | rejected), `received_at`,
  `deadline_at` (30-day SLA, Art. 12(3)), `resolved_at`.
- `patient_consents` — append-only consent events (Art. 7-8): every
  grant/withdraw inserts a row (`purpose`, `granted`, `provided_text`
  verbatim, `granted_at`, `withdrawn_at`). Latest row per
  (patient, purpose) is current; history is never mutated.
- `retention_policies` — per-clinic rules (Art. 5(1)(e)): `data_category`,
  `retention_years`, `legal_hold_until`, `is_active`. These gate erasure
  eligibility.
- `gdpr_erasure_audit_logs` — immutable partial-erasure accountability
  (Art. 17): `erased_categories`, `fields_blanked`, `rationale`, `executed_at`,
  `executed_by`.
- `data_breaches` — breach register (Art. 33-34): `description`,
  `data_involved`, `affected_people`, `status`, `notified_authority_at`.

Migration `gdpr_0001_initial` on own Alembic branch (`gdpr`), depending on
`patients@pat_0003`.

## Erasure semantics (read this first)

**Erasure is partial and never hard-deletes a patient row.** Under Art. 17 a
patient may request deletion, but a clinic may retain data where another legal
basis applies (Art. 17(3) — billing, legal claims, public health). `_erasure`
therefore:

1. Looks up the patient first (clinic-scoped) — unknown/other-clinic
   ids return `None` (404 upstream, error in the tool) before anything is
   written, because the audit table FKs `patient_id`.
2. Looks up active `retention_policies` for the requested `categories`
   (closed vocabulary `email | phone | identity` — anything else is a 422;
   unmapped policy categories always retain).
3. A category is **erasable** only when its policy's `legal_hold_until`
   has passed AND its age window has passed (`retention_years == 0` =
   no age hold, else N years from the patient's `updated_at`).
4. Categories with no policy, unexpired holds, or no field mapping are
   **retained**.
5. For each erasable category, the patient's corresponding identity/PII fields
   (`email`+`billing_email`, `phone`, `national_id`) are set to `NULL`.
6. Every run writes an `ErasureAuditLog` and publishes `gdpr.erasure.executed`.

Sibling modules must not add hard-DELETE for GDPR; if a future full-erasure
feature ships, it must clear rows via a dedicated reversible job, not an
ad-hoc delete.

## Dependencies

`manifest.depends = ["patients"]` — `Patient` PII (identity + contact) is the
subject of consents, DSRs, erasure and export. No other cross-module FK.
Other modules may subscribe to the GDPR events without declaring a dependency.

## Permissions

`gdpr.requests.read/write`, `gdpr.consents.read/write`,
`gdpr.retention.read/write`, `gdpr.audit.read`, `gdpr.breaches.read/write`.
Admin wildcard; dentist sees requests/consents/audit/retention read-only;
hygienist read-only requests; assistant read requests/consents; receptionist
reads+writes requests/consents and reads breaches (front-desk answers most
DSRs).

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `create_gdpr_request` | WRITE | `GdprService.create_request` | `gdpr.requests.write` |
| `list_gdpr_requests` | READ | `GdprService.list_requests` | `gdpr.requests.read` |
| `record_gdpr_consent` | WRITE | `ConsentService.grant_or_withdraw` | `gdpr.consents.write` |
| `list_gdpr_consents` | READ | `ConsentService.list_consents` | `gdpr.consents.read` |
| `create_retention_policy` | WRITE | `RetentionService.create` | `gdpr.retention.write` |
| `execute_partial_erasure` | DESTRUCTIVE | `ErasureService.execute` | `gdpr.requests.write` |

All tools filter by `ctx.clinic_id` and return native values (UUID/datetime).

## Events published

| Event | When | Payload keys |
|---|---|---|
| `gdpr.request.created` | a DSR is created | `clinic_id`, `request_id`, `patient_id`, `request_type` |
| `gdpr.request.status_changed` | a DSR status changes | `clinic_id`, `request_id`, `patient_id`, `from_status`, `to_status`, `changed_by` |
| `gdpr.consent.granted` | consent recorded | `clinic_id`, `consent_id`, `patient_id`, `purpose` |
| `gdpr.consent.withdrawn` | consent withdrawn | `clinic_id`, `consent_id`, `patient_id`, `purpose` |
| `gdpr.erasure.executed` | partial erasure ran | `clinic_id`, `patient_id`, `request_id`, `erased_categories`, `retained_categories` |
| `gdpr.breach.reported` | a breach is created | `clinic_id`, `breach_id`, `affected_people` |

## Lifecycle

`installable=True`, `auto_install=False` (optional compliance module),
`removable=True` with roundtrip uninstall tests.

## Gotchas

- **Every query filters `clinic_id`** — including agent tools. A DSR for a
  patient of another clinic 404s, never leaks.
- **Never hard-delete a patient for GDPR.** Erasure blanks PII; the row stays.
- **A consent withdrawal appends — never mutates.** Re-granting must not
  clear `withdrawn_at`; latest-per-(patient, purpose) is current.
- **`retention_years` runs from the patient's `updated_at`.**
  `0` = no age hold; N > 0 = erasable once N years past `updated_at`
  (minimum-honest anchor until a last-visit provider exists) — and erasure
  still needs any `legal_hold_until` to have passed.
- **Approvals are additive:** `update_request` moves `received → in_progress →
  completed/rejected`; going back to `received` clears `resolved_at`.

## CHANGELOG

See `./CHANGELOG.md`.