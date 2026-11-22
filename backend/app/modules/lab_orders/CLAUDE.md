# lab_orders module

Tracks work sent to external laboratories for a specific patient, with a lifecycle from `sent` through `received` (or `cancelled`).

## Dependencies

`manifest.depends = ["patients", "contacts"]`.

- `patient_id` references `patients.id`.
- `lab_contact_id` references `contacts.id` and must be a `contact_type='lab'` contact of the clinic (400 otherwise, on create and on update; #985).
- Every service query and agent tool is scoped by `clinic_id`.
- The initial Alembic revision declares `depends_on = ("pat_0003", "con_0001")` in addition to the module dependency manifest because migration-graph ordering is separate from module installation ordering.

## Permissions

`lab_orders.read`, `lab_orders.write`.

## HTTP

Routes are mounted under `/api/v1/lab_orders/`.

- GET list/detail — read
- POST create — write, returns 201
- PATCH update/status — write

There is no DELETE: orders are terminated via `status = "cancelled"`
(patient-linked records are never hard-deleted).

## Tools exposed

All handlers wrap `LabOrderService` and are scoped by `ctx.clinic_id`.
Summaries return only structured fields (ids, dates, enums) — no
`notes` / names — so none sets `exposes_free_text`.

| Tool | Category | Permission |
|------|----------|------------|
| `list_lab_orders` | READ | `lab_orders.read` |
| `create_lab_order` | WRITE | `lab_orders.write` |
| `update_lab_order_status` | WRITE | `lab_orders.write` |

## Events

The module emits `lab_order.status_changed` after a successful status transition. No bundled handler consumes it; other optional modules may subscribe without importing `lab_orders`.

## Lifecycle

`installable=True`, `auto_install=False`, `removable=True`.

The module owns two Alembic revisions on the `lab_orders` branch, and the test suite verifies branch-scoped uninstall/reinstall.
