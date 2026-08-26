# Treatment consumables module

Junction linking catalog treatments to the inventory items they
consume, with quantity per link (root canal → 2 anesthetic vials).
Pure mapping — **no stock deduction** (that lands with the inventory
core upgrade #226). `depends: ["catalog", "inventory"]`; writes only to
its own table.

## Public API

Routes mounted at `/api/v1/treatment_consumables/`.

- `GET    /treatment_consumables`              — list links (resolved names), filterable by treatment/item, paginated; `treatment_consumables.read`
- `GET    /treatment_consumables/link-options` — search-based picker data from both modules; `treatment_consumables.read`
- `POST   /treatment_consumables`              — create link (validates both endpoints in-clinic; 409 on duplicate pair, raised from the unique constraint so concurrent creates never surface a 500); `.write`
- `PATCH  /treatment_consumables/{id}`         — update quantity and/or note (omit `note` to keep it, `""` to clear it); `.write`
- `DELETE /treatment_consumables/{id}`         — unlink; `.write`

## Dependencies

`depends: ["catalog", "inventory"]` — real DB-level FKs into both;
CI-enforced against the manifest. Reads them (ADR 0002), never writes.
The migration mirrors this: `tc_0001` declares
`depends_on = ("cat_0004", "inv_0001")` so a fresh `upgrade heads`
creates the referenced tables first, and Alembic tears the branch down
together with `inventory` when its dependency is downgraded
(migration-graph ordering is separate from module install ordering).

## Events

Emits nothing, consumes nothing (pure mapping). See
docs/technical/treatment_consumables/events.md.

## Permissions

`treatment_consumables.read`, `.write`. Default grants: admin full,
dentist read-only.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `get_treatment_consumables` | READ | `TreatmentConsumablesService.list_links` | `treatment_consumables.read` |

Structured mapping data only — no free prose — stays cloud-eligible.
