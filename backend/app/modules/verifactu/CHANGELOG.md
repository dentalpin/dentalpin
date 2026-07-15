# Changelog — verifactu module

## Unreleased

- i18n: add French locale (`fr.json`) with full UI coverage.

- fix(frontend): the queue tabs (Pendientes/Rechazadas/Fallos) rendered
  the same unfiltered list — `listQueue` passed `{ params }`, which
  `useApi` dropped. Switched to the new `useApi` `query` option so the
  `?state=` filter is actually sent (audit S5, #95).

- refactor(perms): migrate hardcoded ``can('verifactu.{settings.read, settings.configure, queue.manage, records.read, environment.promote}')`` strings across the settings pages, queue, ``InvoiceVerifactuSlot`` and ``RejectedGlobalBanner`` to the typed ``PERMISSIONS.verifactu.*`` (new entries in the host permissions config).
- refactor(errors): switch ``catch (e: any)`` to ``catch (e: unknown)`` across ``producer`` / ``queue`` / ``vat-mapping`` / ``certificate`` / settings index / ``InvoiceVerifactuSlot`` and route messages through the shared ``errorMessage`` / ``errorStatus`` helpers.
- chore(migrations): isolate ``vfy_0001`` from the main upgrade
  chain — ``down_revision`` switches from ``tp_0002`` to ``0001``
  (core init) and a new ``depends_on="bil_0001"`` enforces the
  cross-module dependency on the ``invoices`` table declaratively.
  Verifactu is ``removable=True``; with this in place
  ``alembic downgrade verifactu@base`` walks only verifactu
  revisions during uninstall, no other branches affected. The
  ``branch_labels=("verifactu",)`` was already in place.
- perf(records-list): ``/verifactu/records`` counts directly via
  ``COUNT(VerifactuRecord.id)`` instead of materialising the filter
  query as a subquery.
- **AEAT badge en lista y ficha de factura.** Pill `AEAT` con icono +
  color (verde/azul/ámbar/rojo) inyectado vía nuevos slots de billing
  (`invoice.list.row.meta`, `invoice.detail.header.meta`). Tooltip
  con estado completo + mensaje AEAT si rechazada. Renderiza nada
  para clínicas no-ES.
- **Filtro Verifactu en toolbar de lista** (`invoice.list.toolbar.filters`).
  Multi-select con 4 opciones (`Aceptadas / Con avisos / Pendientes /
  Rechazadas`) + chip atajo "Solo problemas" que preselecciona
  rechazadas + con avisos. Counter en el botón cuando hay activas.
- **`compliance_data['ES'].severity`** — nuevo campo derivado escrito
  por verifactu cada vez que toca el registro. Vocabulario genérico
  (`ok|warning|pending|error`) que el filtro de billing entiende sin
  conocer Veri*Factu. Helper puro `services/severity.py::severity_for()`
  mapea state + AEAT error code → severity (incluye lógica
  failed_transient: -2 / >=1000 → error, resto → pending).
- **Mirror extendido** en `submission_queue`. Antes solo se mirroreaba
  `accepted` / `accepted_with_errors` / `rejected` a
  `Invoice.compliance_data`. Ahora también `failed_validation` y
  `failed_transient` para que el badge muestre la verdad sin extra
  fetch.
- **Backfill** `backend/scripts/backfill_verifactu_severity.py` —
  script one-shot que rellena `severity` para invoices anteriores al
  sprint sin tocar las que ya lo tienen.

- **Subsanación con datos modificados** (canon AEAT). The retry
  endpoint now defaults to regenerating the XML + huella from current
  Clinic + Invoice + Settings data and re-queueing as
  `Subsanacion=S` + `RechazoPrevio=X` per RD 1007/2023 + Orden
  HAC/1177/2024. Previously it only re-sent the stored XML verbatim,
  which left rejections un-fixable by data corrections.
- **`POST /verifactu/queue/retry-all`** — bulk regenerate every
  `rejected` record for a clinic in one call (capped at 200). Use
  case: clinic activates Verifactu with mistyped NIF and 50 invoices
  reject at once; admin fixes the NIF and resolves all of them with
  one click.
- **`PATCH /api/v1/billing/invoices/{id}/billing-party`** (added in
  the billing module). Lets the user fix `billing_name` /
  `billing_tax_id` / `billing_address` on an issued invoice when the
  Verifactu hook reports the latest fiscal record is in
  `rejected` / `failed_validation`. Runs `regenerate_record` in the
  same transaction so a single click resolves the rejection.
  Optimistic-lock via `expected_updated_at` echoes Invoice.updated_at.
- **Issue blocker.** `validate_before_issue` now returns 422 when any
  Verifactu record is `rejected` / `failed_validation` for the clinic,
  preventing new invoices from being issued until the existing
  rejection is resubsanated. Guarantees the rejected record stays as
  chain head so regenerate never has to re-sign downstream records.
  `failed_transient` (network) does NOT block — it is retried by the
  worker automatically.
- **Audit trail** for art. 8 RD 1007/2023. New table
  `verifactu_record_attempts` (migration `vfy_0006`) stores the
  pre-regeneration XML + huella + AEAT response of every record that
  is regenerated, so the original rejected payload is preserved for
  auditing even after Subsanación overwrites the parent row. Exposed
  via `GET /verifactu/records/{id}/attempts`.
- **Tagged friendly errors.** `error_messages.friendly_error()` now
  returns `{message, field, suggested_cta}` so the queue and invoice
  UIs render targeted CTAs ("Edit my fiscal data" vs "Edit customer
  data") based on which AEAT validation tripped (4116 emisor vs
  4117/4140 destinatario, etc.).
- **Rejected → email alert.** Submission queue publishes
  `verifactu.record.rejected` after committing the rejection.
  `tasks.py` subscribes and emails clinic admins (template
  `verifactu_record_rejected`) with a personalised CTA. Throttled per
  clinic to one email per 30 min via new column
  `verifactu_settings.last_rejected_alert_at` (migration `vfy_0006`)
  to avoid flooding when a systemic issue rejects 50 records at once.
- **Spanish NIF validator** (`services/nif_validator.py`) — DNI / NIE /
  CIF mod-23 + control digit. Surfaced as advisory warning via
  `GET /verifactu/nif-check?value=X` (on-blur in the frontend); does
  NOT block save / issue.
- **`Invoice.pdf_stale` flag** (billing migration `bil_0002`) flipped
  to `True` after `regenerate_record` so the invoice page can show a
  "PDF outdated, download again" badge — the embedded QR is computed
  from a huella that no longer matches what AEAT will accept.
- **Submission queue mirrors rejected state** into
  `Invoice.compliance_data['ES']['state']` + `error_code` +
  `error_message` so the invoice page renders the rejection banner
  without an extra round-trip.
- **Frontend.** Queue page renames the action button to "Regenerar y
  reenviar" for rejected rows, adds a "Regenerar todos" bulk action,
  shows the per-attempt history modal, and renders a CTA chip ("Edit
  clinic", "Edit customer", "Review lines") computed from the AEAT
  error code. Invoice page renders a red banner with the same two
  CTAs + a modal for editing billing party. Global app banner
  (registered through `app.banners` slot) shows persistently in the
  layout when `rejected_count > 0`.
- Fix: missing i18n keys `verifactu.producer.fields.*` (name, nif,
  idSistema, version + their hints) caused raw keys to render in the
  producer wizard. Added in ES and EN locales.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).
- Stuck-record reaper: APScheduler job (5 min) demotes records stuck
  in `state=sending` for >10 min back to `pending`, so a worker
  crash mid-batch is recovered automatically.
- Curated Spanish AEAT error map (`services/error_messages.py`):
  queue UI surfaces friendly messages for the most common codes
  (103, 1100, 1103, 1142, 1237, 4101, 4102, 4109, 4128, 4153 plus
  sentinels -1 / -2). Raw AEAT description still shown via
  `<details>` for forensics.
- Daily certificate-expiry alert: APScheduler `CronTrigger(hour=8)`
  emails clinic admins when an active cert expires in ≤30 days.
  Reuses `app.core.email.email_service`; throttled per cert to 1
  email batch per 24 h via new
  `verifactu_certificates.last_expiry_alert_at` column
  (migration `vfy_0005`).
- New permission `verifactu.environment.promote` separately gates
  promotion of test → prod on top of `settings.configure`. Default-
  granted only to `admin`.
- Hook now also exports a country-agnostic `compliance_qr_png_b64`
  key (alongside `verifactu_qr_png_b64`) so `billing.pdf` renders
  the QR without knowing about Spain specifically.
- `uninstall()` now also calls `unregister_jobs()` to remove every
  Verifactu APScheduler job from the host scheduler.

## 0.1.0 — initial

- AEAT Veri\*Factu submissions with chained SHA-256 hash.
- Per-clinic FNMT certificate, encrypted at rest.
- Producer wizard with declaración responsable signature.
- Test vs prod toggle with admin confirmation.
- Auto-install disabled; `removable=True` with retention guard.
- Subscribes to `invoice.paid`. Hooks into `invoice.issued` via
  `BillingComplianceHook` (synchronous, not event-bus, due to
  chained-hash invariant).
