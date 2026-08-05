# Tasks module (staff handoff board)

A simple assign-and-mark-done board for staff communication — deliberately
not a chat: no messages, no read receipts, no "typing" indicator, no
online presence. Custom clinic module — standalone, no dependency on any
other plugin module.

## Public API

Routes mounted at `/api/v1/tasks/`.

- `GET    /tasks/assignable-users` — list active clinic staff (id, name, role) for the assignee picker; `tasks.read`
- `GET    /tasks`                  — list, filterable by status/assignee/priority; `tasks.read`
- `POST   /tasks`                  — create (status always starts at `open`); `tasks.write`
- `PATCH  /tasks/{id}`             — edit / reassign / change status; `tasks.write`
- `DELETE /tasks/{id}`             — delete; `tasks.write`

`assignable-users` deliberately does **not** reuse the existing
`GET /auth/users` endpoint in core — that one requires
`admin.users.write` (admin-only), which would make the handoff board
useless for everyone else. This module's own endpoint only needs
`tasks.read`, so any staff member can see who to assign something to.

List/get responses are enriched with `assigned_to_name` and
`assigned_by_name` (joined server-side from the core `users` table).

## Dependencies

`manifest.depends = []` — standalone. FKs to `users.id` don't require a
`depends` entry since `users` is a core table, not a plugin module (same
as `created_by` columns elsewhere in the project).

## Permissions

`tasks.read`, `tasks.write`. **Every role gets read+write** here
(including hygienist, who is read-only in most other custom modules) —
a handoff board only works if all staff can create and complete tasks
for each other, not just admin/front-desk.

## Status lifecycle

`open ↔ done`. Marking done auto-stamps `completed_at` with today's date
if not already set; reopening a task clears it. No "in progress" state —
kept intentionally binary per the clinic's decision for this phase.

## Tools exposed

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_tasks` | READ | `TaskService.list_tasks` | `tasks.read` |
| `create_task` | WRITE | `TaskService.create_task` | `tasks.write` |
| `mark_task_done` | WRITE | `TaskService.update_task` | `tasks.write` |

## Events emitted / consumed

None. A natural future extension: `lab_orders` (Phase 3) could publish
an event when an order becomes "ready", and this module could subscribe
to auto-create a handoff task — not built now, kept as two independent
modules for simplicity.

## Lifecycle

- `installable=True`, `auto_install=True`, `removable=True`.
- Migrations on the `tasks` Alembic branch, chained off the core `0001`
  migration.

## CHANGELOG

See `./CHANGELOG.md`.
