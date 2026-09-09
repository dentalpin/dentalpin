# Changelog — staff_tasks module

## Unreleased

- feat(i18n): Arabic (ar) locale for the module's frontend layer.

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

## 0.1.0 — initial release

- Staff handoff board: internal task CRUD with a guarded status
  lifecycle (`open` → `claimed` → `done`, `cancelled` escape hatch;
  illegal moves return 422). Claiming an unassigned task assigns the
  claimer; `done` stamps `completed_at`.
- Priority (low/normal/high) and due dates; list filters by status,
  assignee and due-before, with server-side pagination.
- Status changes publish `staff_task.created` /
  `staff_task.status_changed` transactionally (ADR 0019); no bundled
  subscriber.
- Agent tools: `list_staff_tasks`, `create_staff_task`,
  `update_staff_task_status`.
- `auto_install=False`, `removable=True`; own Alembic branch with
  uninstall round-trip, tenant-isolation coverage and HTTP-level
  filter/transition tests.
- Board UX: task details shown under the title, "Assigned to" column
  (`assignee_name` in responses), status selector limited to legal
  transitions, clearable status filter, locale-formatted due dates with
  overdue highlight, and error toasts on failed actions. Re-opening a
  claimed task clears the assignee.
- Whole-team read+write by default (collaboration infrastructure);
  EN/ES/FR/DE/HU/PT/TA locales; technical overview/events/permissions
  pages; bilingual user manual.
