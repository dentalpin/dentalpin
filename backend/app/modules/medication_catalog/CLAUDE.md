# Medication catalog module

Clinic-wide medication list (name, dose, unit, form,
prescribable/active status) managed under Settings → Clinical. Seeded
with a 56-item dental starter set via an idempotent seeder. Data source
for prescriptions (document generation). Standalone — `depends: []`.

## Public API

Routes mounted at `/api/v1/medication_catalog/`.

- `GET    /medication_catalog`           — list, search (`q`), form/is_active filters, paginated; `medication_catalog.read`
- `GET    /medication_catalog/{id}`      — single entry; `medication_catalog.read`
- `POST   /medication_catalog`           — create (409 on case-insensitive duplicate); `medication_catalog.write`
- `PATCH  /medication_catalog/{id}`      — edit (409 on rename onto existing); `medication_catalog.write`
- `DELETE /medication_catalog/{id}`      — delete; `medication_catalog.write`
- `POST   /medication_catalog/seed`      — idempotent starter-set seed; `medication_catalog.write`

## Integrity

Names unique per clinic case-insensitively: enforced in the service
(409) AND by a functional unique index `lower(btrim(name))` in mc_0001
(concurrent-create race closed at the DB level).

## Events

Consumes `clinic.created` with an own-session idempotent seeder
(non-transactional by design — see docs/technical/medication_catalog/events.md).
Emits nothing.

## Permissions

`medication_catalog.read`, `medication_catalog.write`. Default grants:
admin full, dentist read-only. Clinics can widen from the module admin UI.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_medications` | READ | `MedicationCatalogService.list_items` | `medication_catalog.read` |

Returns structured reference data only — no free prose — so it stays
cloud-eligible (no `exposes_free_text`).
