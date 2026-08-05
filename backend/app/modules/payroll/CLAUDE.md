# Lab orders module

Tracks work sent to external labs for a specific patient (crown, bridge,
denture, implant, etc.), with a status lifecycle from "sent" through to
"received". Custom clinic module.

## Public API

Routes mounted at `/api/v1/lab-orders/`.

- `GET    /lab-orders`          — list, filterable by patient/lab/status; `lab_orders.read`
- `GET    /lab-orders/{id}`     — single order; `lab_orders.read`
- `POST   /lab-orders`          — create (status always starts at `sent`); `lab_orders.write`
- `PATCH  /lab-orders/{id}`     — edit / change status; `lab_orders.write`
- `DELETE /lab-orders/{id}`     — hard delete; `lab_orders.write`

List/get responses are enriched with `patient_name` and `lab_contact_name`
(joined server-side) so the frontend never has to resolve IDs itself.

## Dependencies

`manifest.depends = ["patients", "contacts"]`.

- FK to `patients.id` — whose work this is.
- FK to `contacts.id` — which lab it was sent to (must be an existing
  contact in the same clinic; validated in `service.py`, does not require
  `contact_type == "lab"` specifically, since a clinic might file a mixed
  lab/supplier under one contact).

Both cross-branch FKs and the synchronous reads of `Patient`/`Contact` in
`service.py` are allowed under ADR 0002 / 0003 because both modules are
declared above.

## Permissions

`lab_orders.read`, `lab_orders.write`. Default role grants: admin full
access; dentist/assistant/receptionist read+write; hygienist read-only.

## Status lifecycle

`sent → in_progress → ready → received`, with `cancelled` as an
alternate terminal state. Setting `status=received` without an explicit
`received_date` auto-stamps today's date.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_lab_orders` | READ | `LabOrderService.list_orders` | `lab_orders.read` |
| `create_lab_order` | WRITE | `LabOrderService.create_order` | `lab_orders.write` |
| `update_lab_order_status` | WRITE | `LabOrderService.update_order` | `lab_orders.write` |

## Events emitted / consumed

None (kept simple for v0.1 — a natural extension would be publishing
`lab_order.status_changed` for the future task-board module, Phase 5, to
consume for handoff notifications).

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- Migrations on the `lab_orders` Alembic branch, chained off the core
  `0001` migration (cross-branch FKs to `patients`/`contacts` are safe;
  the module loader installs dependencies first per `manifest.depends`).

## CHANGELOG

See `./CHANGELOG.md`.
