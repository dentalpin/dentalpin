# Changelog — activity_journal module

## Unreleased

- Subscribe to `document.generated` (the documents module publishes it
  transactionally with `db=db`), so generated PDFs land in the journal
  with the acting user (`created_by`) when known.

- feat(i18n): Arabic (ar) locale for the module's frontend layer.


## 0.1.0 — initial release

- Append-only journal of transactionally-published events (25 event
  types across agenda, budgets, billing/payments, patients, recalls,
  odontogram treatments, lab orders and treatment plans), with rows
  written inside publishers' transactions (ADR 0019).
- Read-only HTTP surface with event-type/patient/date filters and
  pagination; per-entry payload viewer on the frontend.
- Agent tool `search_activity` (`exposes_free_text=True`).
- Sidebar entry (`nav.journal`) gated on `activity_journal.read`.
- `auto_install=False`, `removable=True`, own Alembic branch
  (`activity_journal`), uninstall round-trip + tenant isolation +
  transactional-handler tests.
- Admin-only role permissions by default; clinics can widen from the
  module admin UI.
- Docs: technical overview/events/permissions pages, user manual en+es.
