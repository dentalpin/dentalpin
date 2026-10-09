# Changelog — recall_reminders module

## Unreleased

- test(#552): branch-scoped uninstall round-trip test (heads, branch downgrade, reinstall).

- `due_month` humanization fixed: the event payload carries the full
  ISO date (`"2026-09-01"` — `Recall.due_month` is a `Date`), but the
  handler parsed `"%Y-%m"`, so production emails would have shown the
  raw ISO string. Tests encoded the wrong payload shape and are fixed
  too.
- `patients` declared in `manifest.depends` (the handler reads
  `Patient` for the template context — required by the cross-module
  import guard) and the `Patient` query is now clinic-scoped per the
  multi-tenancy rule.
- Handler is now transactional (ADR 0019): declares `db`, runs inside
  `recalls`' publish transaction in a savepoint, no longer opens its
  own session or commits. `recalls/service.py`'s `RECALL_CREATED`
  publish now passes `db=db`. Previously the handler flushed the
  queued message but never committed its own session — every recall
  reminder was silently rolled back when the session closed, so none
  could ever actually have been sent (caught by CI's transactional
  test guard, `tests/test_event_bus_transactional.py`).
- Context now includes `patient_name` and `clinic_name`; `due_month`
  is humanized (`"September 2026"`, not the raw `"2026-09-01"`).
- Ships `backend/templates/email/{locale}/recall_reminder.html` for
  en/es/fr/pt/ta — no per-clinic template setup required. Wording
  reads as "we've scheduled your next check-up for {month}" rather
  than "you're due", since this fires when the recall is *created*
  (often ~6 months before the actual due date).
- Added `rr_0001`, a no-op migration on its own branch — required for
  `removable=True` to pass `module_branch_is_isolated` even with no
  tables of its own.
- Added `docs/technical/recall_reminders/overview.md` and `events.md`.
- Dropped fork-specific "Phase 6 of the custom roadmap" framing and
  the `"Clinic Custom"` author placeholder.

## 0.1.0 (prior)

- Initial version: subscribes to `RECALL_CREATED`, enqueues a
  `recall_reminder` notification via the existing gateway. No models,
  no UI — pure connector.
