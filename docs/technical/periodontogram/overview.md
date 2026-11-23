---
module: periodontogram
last_verified_commit: 411343e
---

# Periodontogram — technical overview

Owns SEPA periodontal exams: dated, immutable snapshots of every
permanent tooth with mobility / prognosis / furcation / probing
metrics across six sites. Optional and removable (`installable=True`,
`auto_install=False`, `removable=True`).

Module code lives at `backend/app/modules/periodontogram/`. The
implementation plan and ADR background are in
[`docs/technical/periodontogram-plan.md`](../periodontogram-plan.md)
and [`docs/adr/0013-periodontogram-snapshot-model.md`](../../adr/0013-periodontogram-snapshot-model.md).

## Architecture in 30 seconds

```
┌──────────────────────────┐         pre-fills           ┌────────────────────┐
│ periodontogram_snapshots │ ── reads OdontogramService ─► tooth_records (odo)│
└──────────────────────────┘                              └────────────────────┘
         │ 1:N
         ▼
┌──────────────────────────┐
│  periodontogram_teeth    │ ── one row per permanent FDI tooth (11–48)
└──────────────────────────┘
         │ 1:N
         ▼
┌──────────────────────────┐
│  periodontogram_sites    │ ── six rows per tooth (MV, V, DV, ML, L, DL)
└──────────────────────────┘
```

Each exam is one `snapshot` row. While it is `status='draft'` the
clinician edits any cell; the partial unique index
`uq_perio_snap_one_draft_per_patient` allows **at most one draft per
patient**. Closing the snapshot freezes it, persists the SEPA
indices on the row as JSONB, and publishes
`periodontogram.snapshot.closed`.

Three relational tables (not JSONB) so analytical queries against
mean CAL, deep-pocket count and per-site bleeding all run as plain
SQL with native indexes. See ADR 0013 for the trade-off rationale.

## API surface

Routes mounted at `/api/v1/periodontogram/`.

### Patient-scoped

| Verb   | Path                                | Permission              |
|--------|-------------------------------------|-------------------------|
| GET    | `/patients/{patient_id}/snapshots`  | `periodontogram.read`   |
| GET    | `/patients/{patient_id}/timeline`   | `periodontogram.read`   |
| GET    | `/patients/{patient_id}/draft`      | `periodontogram.read`   |
| POST   | `/patients/{patient_id}/draft`      | `periodontogram.write`  |

### Snapshot-scoped

| Verb   | Path                                                | Permission              |
|--------|-----------------------------------------------------|-------------------------|
| GET    | `/snapshots/{snapshot_id}`                          | `periodontogram.read`   |
| GET    | `/snapshots/{snapshot_id}/indices`                  | `periodontogram.read`   |
| PATCH  | `/snapshots/{snapshot_id}/teeth/{tooth_number}`     | `periodontogram.write`  |
| PATCH  | `/snapshots/{snapshot_id}/teeth/{tn}/sites/{code}`  | `periodontogram.write`  |
| POST   | `/snapshots/{snapshot_id}/close`                    | `periodontogram.write`  |
| DELETE | `/snapshots/{snapshot_id}`                          | `periodontogram.write`  |

All endpoints flow through `get_clinic_context` and filter by
`clinic_id` — multi-tenancy guarantee per the root `CLAUDE.md`.
PATCHes on closed snapshots return **409**; cross-clinic lookups
return **404**; DELETE on a closed snapshot returns 409.

## Coupling with `odontogram`

Declared via `manifest.depends = ["patients", "odontogram"]`.
**Read-only, no FK**: at draft creation the service calls
`OdontogramService.get_patient_odontogram` plus one Treatment query
(`status='performed'`, not soft-deleted) to seed `is_present` /
`is_implant` flags on the snapshot's tooth rows. A tooth is absent
when its `ToothRecord.general_condition` is `missing` or it carries a
`missing` finding or an `extraction` treatment — the odontogram UI
records absence as a Treatment, never on `general_condition` — the
same rule the chart uses to draw a tooth faded. A performed `implant`
wins over absence (`is_present=True, is_implant=True`). Planned
treatments do not change the flags.
Snapshots persist `tooth_number` (FDI int) only, never
`tooth_records.id` — uninstalling odontogram would not orphan any
periodontogram row.

## Data model snapshot

See the migration `perio_0001_initial.py` for column-level detail.
Key constraints:

- `ck_perio_snap_status`: `status IN ('draft', 'closed')`.
- `ck_perio_snap_closed_pair`: `closed_at` / `closed_by` are
  populated iff `status='closed'`.
- `ck_perio_tooth_fdi`: tooth_number in 11..48 with quadrant + position
  in valid SEPA ranges.
- `ck_perio_site_code`: `site_code IN ('MV','V','DV','ML','L','DL')`.
- `ck_perio_site_pd_range`: probing depth 0–15 mm.

## SEPA indices

Computed by `app.modules.periodontogram.indices`:

- `bop_pct` — % of measured sites with bleeding on probing.
- `pi_pct` — % of measured sites with plaque.
- `cal_mean_mm` — mean clinical attachment level (PD + GM) over
  sites where both values exist.
- `deep_pockets_count` — distinct teeth with at least one site
  ≥ 5 mm.

Only sites with `probing_depth_mm IS NOT NULL` count toward
percentage denominators — empty sites are "not measured", not
"measured at zero".

## Frontend layer

`backend/app/modules/periodontogram/frontend/`. Single slot
registration: `patient.diagnosis.subtabs` → `PeriodontogramView.vue`.
The host (`patients` module's `DiagnosisModeContainer.vue`) renders
its existing `<DiagnosisMode>` directly when the slot has no
entries — uninstalling the module restores the pre-slot UI verbatim.

The chart reuses the odontogram's lateral SVG paths via
`getLateralPath` + `getToothTransform`, flipped vertically on the
palatal/lingual rows. Heatmap tones come from `usePerioHeatmap`.
Per-cell edits stream through `usePeriodontogramSession` (600 ms
debounce) and `flushPending` runs before close so the closed
snapshot always sees the latest payload.

## Tests

- `backend/tests/test_uninstall_roundtrip.py::test_periodontogram_uninstall_roundtrip_is_branch_scoped`
- `backend/tests/modules/periodontogram/test_snapshot_lifecycle.py`
- `backend/tests/modules/periodontogram/test_api_validation.py`
- `backend/tests/modules/periodontogram/test_indices_calc.py`
- `backend/tests/modules/periodontogram/test_odontogram_coupling.py`

## Related ADRs

- [`docs/adr/0013-periodontogram-snapshot-model.md`](../../adr/0013-periodontogram-snapshot-model.md)
- [`docs/adr/0001-modular-plugin-architecture.md`](../../adr/0001-modular-plugin-architecture.md)
- [`docs/adr/0002-per-module-alembic-branches.md`](../../adr/0002-per-module-alembic-branches.md)
- [`docs/adr/0003-event-bus-over-direct-imports.md`](../../adr/0003-event-bus-over-direct-imports.md)
