# Verifactu module

Spanish AEAT compliance (Veri\*Factu, RD 1007/2023). The deep
operator-facing guide is `./README.md` — start there for producer
responsibility, deployment models, and the AEAT integration. This
file is the agent quick reference.

## Public API

Routes mounted at `/api/v1/verifactu/`. Settings, certificate
management, queue inspection, records.

## Dependencies

`manifest.depends = ["billing", "catalog"]`.

## Permissions

`verifactu.settings.{read,configure}`,
`verifactu.records.read`,
`verifactu.queue.manage`.

## Events emitted

- `verifactu.record.rejected` — published by `submission_queue` after
  AEAT marks a record `Incorrecto`. Payload: `record_id`, `invoice_id`,
  `clinic_id`, `serie_numero`, `codigo_error`, `descripcion_error`,
  `friendly_message`, `field`, `suggested_cta`. Consumed internally by
  `tasks._notify_rejected` to email clinic admins (throttled 30 min
  via `verifactu_settings.last_rejected_alert_at`).

## Events consumed

- `invoice.paid` → updates `compliance_data['ES']` on the invoice.

The producer reaction to `invoice.issued` happens via
`BillingComplianceHook` (synchronous hook), **not** via the event bus,
because the chained-hash invariant requires deterministic ordering.
See `hook.py` and `README.md` for the architecture.

## Lifecycle

- `auto_install=False` — operator activates from Admin → Modules.
- `removable=True`, but `uninstall()` blocks if any record reached
  `accepted` state (legal retention, 4 years).
- Migrations on the `verifactu` Alembic branch.

## Gotchas

- **No NIF on a credit note means R5, not R1** (#1049): AEAT only accepts
  a record without Destinatarios for F2 and R5. A rejected R1 blocked the
  clinic's issuing and regenerating rendered R1 again.

- **Producer wizard must be filled before `prod`.** The backend rejects
  enabling Veri\*Factu in production until the declaración is signed.
- **Chained hash invariant.** Records form a SHA-256 chain. Skipping or
  reordering breaks the chain and AEAT will reject everything after.
  Hence the synchronous `BillingComplianceHook` instead of the event
  bus on `invoice.issued`.
- **Issue blocked while a record is rejected.** `validate_before_issue`
  returns 422 if any record is in `rejected` / `failed_validation` for
  the clinic. This is intentional: it guarantees the rejected record
  is always the chain head, so `regenerate_record` can rewrite the
  same row without having to re-sign downstream records. `failed_transient`
  (network) does NOT block — the worker retries automatically.
- **Subsanación regenerates the XML in place.** `regenerate_record`
  recomputes huella + XML from current data and overwrites the parent
  row. The previous attempt is preserved in `verifactu_record_attempts`
  for art. 8 RD 1007/2023 trazabilidad. Inmutabilidad sólo aplica a
  registros aceptados (libro fiscal AEAT) — los rechazados son
  modificables hasta que la AEAT los acepte.
- **`Invoice.pdf_stale=True` after regenerate.** The embedded QR is
  computed from a huella that no longer matches the new submission, so
  any PDF already downloaded / emailed is stale. Frontend shows a
  badge prompting re-download.
- **`compliance_data['ES'].severity` is the source of truth for the
  badge + filter.** Vocabulary: `ok | warning | pending | error`
  (defined in `services/severity.py::severity_for`). Verifactu writes
  it on every transition (issue, queue update, regenerate). Billing
  filters generically by this field over any country key — never
  imports verifactu, never learns Spanish-specific record states.
  When adding a new state to `RECORD_STATES`, update `severity_for`
  in the same change so the badge stays consistent.
- **Per-clinic FNMT certificate.** Encrypted at rest with Fernet
  derived from `SECRET_KEY` — rotating `SECRET_KEY` requires
  re-encrypting certificates. Document this in any ops runbook change.
- **Test vs prod environments.** `prewww1.aeat.es` for test,
  `www1.agenciatributaria.gob.es` for prod. Flipping requires admin
  confirmation in the wizard.
- **Producer responsibility is per-deployment.** SaaS operator,
  self-hosting clinic, or integrator — they each carry it differently.
  See `README.md` "Producer responsibility".

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md` (and the
  documented exception — `BillingComplianceHook`)
- `docs/adr/0004-bsl-license.md`

## CHANGELOG

See `./CHANGELOG.md`.
