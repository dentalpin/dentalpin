# treatment_consumables — overview

Junction module linking a **catalog treatment** to the **inventory
items** it consumes, with a quantity per link (e.g. root canal → 2
anesthetic vials).

**Pure mapping**: no stock deduction logic here. When the inventory
core upgrade (#226) adds consumption tracking, it will subscribe to
treatment events itself rather than this junction writing stock.

## Design

- `depends: ["catalog", "inventory"]` — declared so the loader mounts
  this module after both, and because the FKs are real: CI enforces
  cross-module foreign keys against the depends declaration.
- Reads both modules to validate links (both endpoints must exist in
  the same clinic → 404 otherwise) and to resolve display names;
  writes only to its own table.
- The (clinic, treatment, item) triple is unique at the DB level; the
  API answers 409 on duplicates.
- Quantities are positive decimals with a unit shown from the linked
  inventory item ("2 vials").

## Frontend

`/treatment-consumables`: history table of every link plus a create
dialog with **search-based pickers into both dependency modules**, fed
by a single `GET /link-options?q=` endpoint gated on this module's own
read permission (so no extra catalog/inventory grants are needed to
use it).

## Install policy

Optional module: `auto_install=False`, `removable=True`. Requires
`catalog` and `inventory` to be installed first (enforced by the
manifest loader). Default roles: admin full, dentist read-only.
