# Changelog — staff_tasks module

## Unreleased

- fix(#863): `assignee_id` must be a member of the task's clinic, on create and on update. An unknown id was a 500, and another clinic's user was stored with their name shown in `assignee_name`. Both now return 400.

- fix: date-only fields (`YYYY-MM-DD`) are parsed as local midnight
  (`parseDateOnly`, host `utils/wallClock.ts`) instead of `new Date(s)`, which
  is UTC midnight and rendered every such date one day early in zones behind
  UTC — all of the Americas.
- fix(#677): the `update_staff_task_status` tool parameter `task_id` is
  typed `UUID` instead of `str = Field(min_length=1)`, a constraint that
  admitted any non-empty string.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- fix(#522): the overdue check compared `due_date` against the UTC day, so
  east of UTC a task stayed unmarked for the length of the offset after local
  midnight. Now uses `toISODate`.

- feat(#232): sidebar entry grouped under the Practice header (`nav.section` "practice").
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
