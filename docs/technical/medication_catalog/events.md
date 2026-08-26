# medication_catalog — events

The module emits **no events**. Catalog entries are reference data;
nothing else needs to react to their lifecycle asynchronously.

## Consumed

| Event | Handler | Mode |
| --- | --- | --- |
| `clinic.created` | `on_clinic_created` → `seed_medications` | **own session (non-transactional)** |

Why non-transactional: `clinic.created` is published *after* the signup
transaction commits and **without a `db=` session** (the bus raises
`RuntimeError` if a transactional handler receives no session). This is
the exact precedent of the `catalog` module's seeder (issue #183):
the handler opens its own session via `async_session_maker`, seeds
idempotently, commits — and logs failures instead of raising, since a
seeding gap must never break clinic signup. `POST
/medication_catalog/seed` repairs an empty list on demand.
