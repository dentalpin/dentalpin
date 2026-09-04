# Changelog — gdpr module

## Unreleased

- Maintainer-review fixes (PR #374, part of #44): closed erasure
  vocabulary `ErasureCategory` (`email | phone | identity`, 422 on anything
  else) in the schema and tool args so an erasure can never report a
  category it cannot blank; erasure of unknown/other-clinic patients
  returns `None` (404 upstream, tool error) before touching the audit
  table; retention windows run from the patient's `updated_at` anchor
  (`0` = no age hold, else N years); consents are append-only (one row per
  event, latest per purpose is current); dropped `DELETE /requests/{id}`
  (DSRs are Art. 5(2) accountability records); `datetime.now(UTC)`
  everywhere; deleted dead `ExportService.record_export`; dropped the
  `definition_year` leftover; docs state the v1 scope (ticket tracker, no
  Art. 21 objection yet, export = identity+consents+DSRs, no frontend).
- Initial module (issue #44): GDPR (EU 2016/679) compliance for a clinic.
- Added 5 models on their own Alembic branch (`gdpr`): `gdpr_requests`
  (DSR, Art. 15-20), `patient_consents` (Art. 7-8), `retention_policies`
  (Art. 5(1)(e)), `gdpr_erasure_audit_logs` (Art. 17 accountability),
  `data_breaches` (Art. 33-34).
- DSRs carry a 30-day SLA (`deadline_at` from `received_at` via
  `SlaCalculator`); status transitions auto-stamp `resolved_at`.
- Consents are append-only: every grant/withdraw inserts a row, so the
  full trail (including withdrawals) survives; a withdrawal is never
  destructive.
- Partial erasure (Art. 17) blanks patient identity/PII fields once the
  governing retention policy allows; the patient row is never hard-deleted.
  Every run writes an immutable `ErasureAuditLog` and publishes
  `gdpr.erasure.executed`.
- Portability export endpoint (`GET /gdpr/export/{patient_id}`, Art. 20)
  returns a machine-readable identity + consents + DSR snapshot.
- Six new `EventType` values published by the services:
  `gdpr.request.created`, `gdpr.request.status_changed`,
  `gdpr.consent.granted`, `gdpr.consent.withdrawn`,
  `gdpr.erasure.executed`, `gdpr.breach.reported`.
- RBAC: `gdpr.requests.read/write`, `gdpr.consents.read/write`,
  `gdpr.retention.read/write`, `gdpr.audit.read`, `gdpr.breaches.read/write`;
  admin wildcard, therapist read-only, front-desk read/write for DSRs/consents.
- Agent tools exposed: `create_gdpr_request`, `list_gdpr_requests`,
  `record_gdpr_consent`, `list_gdpr_consents`, `create_retention_policy`,
  `execute_partial_erasure` (wrapping the GDPR services, `ctx.clinic_id`-filtered).
- Migration `gdpr_0001_initial` on own Alembic branch (`gdpr`), depending on
  `patients@pat_0003`.
- `removable=True` — supports full uninstall with roundtrip tests.
- Registered `app/modules/gdpr` in `backend/alembic.ini` `version_locations`
  so the Alembic CLI graph (heads/upgrade) resolves `gdpr_0001` (CI parity).
- Registered `gdpr` in `pyproject.toml` module entry points so the module is
  discoverable in production (`DENTALPIN_DEV_MODULE_SCAN=False`); closes the
  entry-point parity gap reported by `tests/test_entry_point_parity.py`.