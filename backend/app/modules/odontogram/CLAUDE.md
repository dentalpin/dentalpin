# Odontogram module

Dental charting: tooth state, surfaces, conditions, clinical
treatments per tooth.

## Public API

Routes mounted at `/api/v1/odontogram/`.

## Dependencies

`manifest.depends = ["patients", "catalog"]`.

## Permissions

`odontogram.read`, `odontogram.write`,
`odontogram.treatments.read`, `odontogram.treatments.write`.

## Events emitted

- `odontogram.treatment.added`
- `odontogram.treatment.status_changed`
- `odontogram.treatment.performed`
- `odontogram.treatment.deleted`

(Surface/tooth update events `odontogram.surface.updated`,
`odontogram.tooth.updated`, `odontogram.condition.changed` are declared
in `EventType` but not yet emitted by code — TODO.)

## Events consumed

None.

## Lifecycle

- `removable=False`. Treatment_plan, budget depend on tooth treatments.

## Gotchas

- **FDI numbering is strict** (11–48 permanent, 51–85 deciduous).
  Validate at the boundary; don't trust caller-supplied tooth ids.
- **Treatments fired on `performed`** are the trigger for budget +
  treatment_plan sync. Idempotency matters — a re-fire must not
  double-charge. `perform` locks the row and refuses a treatment that is
  already `performed` (`TreatmentAlreadyPerformedError` → 409, #891): a
  sessioned treatment finalized with `unit_price: null` would otherwise
  book its full price on a second perform. treatment_plan's item
  finalization passes `refuse_if_performed=False` (it publishes with no
  price): the edit modal can mark the treatment performed before the
  item's last session (#897).
- **`treatment.deleted` and `treatment.status_changed` are published
  transactionally** (`db=db`): payments deletes the treatment's
  NULL-session earned row when it is deleted or leaves `performed` (#896).
  The deleted payload carries `old_status`.
- **`price_snapshot` is the whole treatment's price** (#1014): per-tooth and
  per-role pricing are already applied, so `unit_price` carries it as is.
- **`unit_price: null` on `treatment.performed` is a contract**, not a
  missing field: `perform(publish_price=False)` is how treatment_plan
  finalizes a sessioned item whose amounts were already booked
  per-session by payments. Subscribers must not attribute revenue when
  the price is null.
- **Surface state lives in JSONB** (`constants.py` defines the keys).
  Migrations that change the shape must include data migrations.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0003-event-bus-over-direct-imports.md`

## CHANGELOG

See `./CHANGELOG.md`.
