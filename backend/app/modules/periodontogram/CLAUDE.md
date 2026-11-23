# Periodontogram module

SEPA-standard periodontal charting: dated snapshots, six probing sites per
tooth, computed BoP/PI/CAL indices. **Optional, removable**.

## Public API

- Routes mounted at `/api/v1/periodontogram/`.
- PR-1 ships an empty router; endpoints land in PR-2.
- Planned (see `docs/technical/periodontogram-plan.md` §7):
  - `GET    /patients/{id}/snapshots`                        — `periodontogram.read`
  - `GET    /patients/{id}/timeline`                          — `periodontogram.read`
  - `GET    /patients/{id}/draft`                             — `periodontogram.read`
  - `POST   /patients/{id}/draft`                             — `periodontogram.write`
  - `GET    /snapshots/{id}`                                  — `periodontogram.read`
  - `PATCH  /snapshots/{id}/teeth/{tn}`                       — `periodontogram.write`
  - `PATCH  /snapshots/{id}/teeth/{tn}/sites/{site}`          — `periodontogram.write`
  - `POST   /snapshots/{id}/close`                            — `periodontogram.write`
  - `DELETE /snapshots/{id}`                                  — `periodontogram.write` (draft only)
  - `GET    /snapshots/{id}/indices`                          — `periodontogram.read`

## Dependencies

`manifest.depends = ["patients", "odontogram"]`. Reads `OdontogramService`
at draft creation to pre-fill `is_present` / `is_implant` per tooth:
absent = `general_condition == "missing"` or a performed, non-deleted
`missing` / `extraction` Treatment (the UI only writes the Treatment);
a performed `implant` overrides absence.
**No FK** to `tooth_records` — uninstall stays clean.

## Permissions

`periodontogram.read`, `periodontogram.write`.

## Events emitted

| Event | When | Payload keys |
|---|---|---|
| `periodontogram.snapshot.closed` | snapshot transitions draft → closed (PR-3) | `snapshot_id`, `patient_id`, `clinic_id`, `indices`, `closed_at`, `closed_by` |

## Events consumed

| Event | Handler | Effect |
|---|---|---|
| `odontogram.treatment.performed` | `on_odontogram_treatment_performed` | PR-1: log only. PR-3: refresh active draft flags when treatment changes physical state. |
| `patient.archived` | `on_patient_archived` | PR-1: log only. PR-3: discard active draft. |

## Lifecycle

- `installable=True`, `auto_install=False` (optional module — manual
  activation from admin UI), `removable=True`.
- Alembic branch: `branch_labels=("periodontogram",)`. Branch-scoped
  uninstall via `alembic downgrade periodontogram@-1` drops only this
  module's three tables.

## Gotchas / non-obvious invariants

- **Permanent dentition only.** FDI 11–48. DB CHECK rejects deciduous
  numbers — periodontogram exams are clinically permanent-tooth only.
- **One draft per patient.** Partial unique index
  `uq_perio_snap_one_draft_per_patient` blocks a second draft until the
  first closes or is discarded.
- **Snapshots are immutable once closed.** No "reopen" in MVP; corrections
  require a new session.
- **Index computation is the source of truth at close.** `snapshot.indices`
  is a JSONB cache populated on transition to `closed` — recompute via
  `indices.compute_indices(sites)` if you ever need to backfill.
- **No `clinical_notes` polymorphic owner.** `clinical_notes` is
  `removable=False`; pushing a new `owner_type` from a removable module
  would leave orphan rows on uninstall. Notes live as a plain `notes`
  TEXT column on the snapshot.
- **No FK to odontogram.** Coupling is via service read at draft creation
  and via the event bus. Do not add cross-module FKs.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0002-per-module-alembic-branches.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`
- `docs/adr/0014-periodontogram-snapshot-model.md` *(pending)* — rationale
  for immutable dated snapshots over event sourcing.

## CHANGELOG

See `./CHANGELOG.md`.
