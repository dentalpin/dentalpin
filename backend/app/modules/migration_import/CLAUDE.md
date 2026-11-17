# migration_import module

DPMF importer. Optional, installable/removable. Issue #78.

Reads a `.dpm` file produced by [dental-bridge](https://github.com/dentaltix/dental-bridge),
validates it (magic bytes + integrity hash + format version), and
hydrates the current clinic by calling each target module's service.

## Public API

Routes mounted at `/api/v1/migration_import/`.

- `POST   /jobs`                       — `migration_import.job.write`. Upload `.dpm`.
- `POST   /jobs/{id}/validate`         — `migration_import.job.write`. Decrypt/decompress/verify hash.
- `POST   /jobs/{id}/preview`          — `migration_import.job.read`. Entity counts + sample rows + verifactu detection.
- `POST   /jobs/{id}/proposals`        — `migration_import.job.execute`. Dry-run catalog mapper, persist per-row `MappingDecision`. Idempotent.
- `GET    /jobs/{id}/proposals`        — `migration_import.job.read`. Paginated list filterable by `operator_action` and `proposed_action`.
- `PATCH  /jobs/{id}/proposals/{canonical_uuid}` — `migration_import.job.execute`. Operator decision: accepted / relinked / create_new / ignored.
- `POST   /jobs/{id}/proposals/bulk_accept` — `migration_import.job.execute`. Accept every pending proposal whose score ≥ `min_score` (default 0.9).
- `POST   /jobs/{id}/execute`          — `migration_import.job.execute`. Runs mappers as a BackgroundTask. Honours `MappingDecision` when present.
- `GET    /jobs`                       — `migration_import.job.read`.
- `GET    /jobs/{id}`                  — `migration_import.job.read`.
- `GET    /jobs/{id}/warnings`         — `migration_import.job.read`.
- `POST   /jobs/{id}/binaries`         — `migration_import.binary.write`. Sync agent uploads a binary; matched by sha256.

## Dependencies

`manifest.depends = ["patients", "agenda", "schedules", "treatment_plan", "billing", "payments", "media"]`.

**`verifactu` is intentionally NOT in `depends`.** Portuguese/French
clinics import without it. The fiscal-document mapper detects it at
runtime through `module_registry.is_active("verifactu")` and gates
legal-hash preservation behind an operator opt-in checkbox shown in
the preview step.

## Permissions

`migration_import.job.read`, `job.write`, `job.execute`, `binary.write`.

Default `role_permissions` grants `*` to `admin` only — operators must
be promoted to admin to run a migration.

## Events emitted

| Event | When | Payload |
|---|---|---|
| `migration.job.started`     | execute begins                 | `job_id`, `clinic_id` |
| `migration.job.completed`   | execute finishes successfully  | `job_id`, `clinic_id`, `total_entities`, `warnings_count` |
| `migration.job.failed`      | unhandled exception            | `job_id`, `clinic_id`, `error` |
| `migration.binary.resolved` | sync agent uploaded a matching binary | `job_id`, `staging_id`, `document_id` |

Plus every event the mapped service publishes naturally
(`patient.created`, `payment.recorded`, …).

## Events consumed

`migration.entity.persisted` — internal progress signal published by
mappers. Used to bump `ImportJob.processed_entities`.

## Lifecycle

- `installable=True`, `auto_install=False` (opt-in from admin UI),
  `removable=True`. Uninstall round-trip lives in
  `backend/tests/test_uninstall_roundtrip.py`.
- Imported rows survive uninstall — they belong to `patients`,
  `payments`, etc., not to us. We only drop our staging tables.

## Gotchas

- **Gesdén-specific tables live in ``mappers/_gesden_catalog.py``.**
  ``IdTipoODG`` (46-value ``TTipoOdg`` master) drives clinical_type,
  treatment_scope, requires_surfaces, category, pricing strategy AND
  the abbreviation alias map. Both ``catalog.py`` and
  ``applied_treatment.py`` consume the same tables — adding a new
  IdTipoODG value lights up everywhere. The module asserts coverage
  at import time so silent drift is impossible.
- **Operator overrides win.** When ``MappingDecision.operator_action``
  is not ``pending``, ``CatalogItemMapper.apply`` honours it instead
  of running the matcher: ``accepted`` uses the proposal, ``relinked``
  uses ``operator_target_id``, ``create_new`` forces creation in
  ``operator_target_category_key``, ``ignored`` marks the row as
  skipped (no resolver mapping, no catalog row).
- **Patient ledger source of truth: ``DeudaCli``.** `DebtMapper`
  is the only mapper that writes ``PatientEarnedEntry`` — it
  consumes canonical ``debt`` rows (one per non-anulado, non-
  uncollectible Gesdén receivable with ``Adeudo > 0``). The
  ``applied_treatment`` mapper used to derive earned from
  ``TtosMed.Importe`` (the catalog reference price) but that
  over-books by ~50% in real exports because most realised
  treatments are off-books (staff / family / courtesy work,
  "incluido" bundle lines, pre-billing-system historicals).
  Clinical history is independent: Treatment, PlannedTreatmentItem,
  TreatmentTooth, ToothRecord conditions and ClinicalNote all land
  regardless of whether ``DeudaCli`` ever materialised, so the
  odontogram + plan view still surface every realised treatment.
  ``DebtMapper`` registers a sidecar ``applied_treatment_record``
  resolver entry from ``AppliedTreatmentMapper`` to recover the
  Treatment row for catalog/professional/performed_at snapshots and
  to honour the
  ``(treatment_id, source_session_id)`` uniqueness constraint —
  if you add another writer of ``PatientEarnedEntry`` here, use a
  uuid5-derived ``source_session_id`` to keep multi-phase rows
  collision-free.
- **Opening balances.** A canonical `debt` row with JSON boolean
  `opening_balance: true` is recorded with
  `source_event="migration_import:opening_balance"`. Producers should
  supply one stable `canonical_uuid` per patient opening balance. Like
  other debt rows, it accepts a signed `owed_amount` and an optional
  `description` (stored up to 160 characters). A negative amount creates
  ledger credit. A blank or missing description uses the mapper's
  default label.
- **Invoice line catalog links.** `fiscal_document_line` accepts
  `treatment_uuid` or `treatment_variant_uuid` as optional canonical
  catalog references. Resolution prefers the treatment template, then the
  tariff variant, then the existing `applied_treatment_uuid` path. Unmapped
  catalog references emit a warning. A line with no resolved catalog item
  can still be imported using its fiscal snapshot.
- **`clinic_id` always comes from `ctx`**, never from the DPMF payload.
  Mappers that read `clinic_id` from the file are a tenancy bug.
- **External IDs are never used as FKs.** Every cross-entity reference
  goes through `MappingResolver`. The `EntityMapping` table is the
  only source of truth for "this canonical_uuid became this dentalpin
  UUID".
- **Idempotency is per `(clinic_id, source_system, canonical_uuid,
  entity_type)`.** Re-running execute on the same job is safe.
- **No rollback in v1.** If a job fails halfway, the partial state
  stays. Admin restores from backup if catastrophic. Document this in
  the UI.
- **The passphrase is never persisted.** Held in process memory only
  during validate/preview.
- **Binaries go through `media.DocumentService`** so the storage path,
  thumbnails, MIME validation and clinic-scoping are honoured.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
