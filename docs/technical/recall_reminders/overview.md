---
module: recall_reminders
last_verified_commit: 0000000
---

# recall_reminders — overview

Connects `recalls` (builds the call-back list, publishes
`RECALL_CREATED`, but "never sends" by its own design) to
`notifications` (a full delivery gateway with consent/template/channel
resolution) — nothing was calling it for recalls before this module
existed.

## What it is

Pure event glue: one subscriber function, no models, no API routes, no
UI of its own.

- **`_on_recall_created`** subscribes to `EventType.RECALL_CREATED` and
  calls `NotificationGateway.enqueue(notification_type="recall_reminder", ...)`
  for that patient. All consent checking, channel selection, and
  template rendering happens inside the existing gateway, unchanged —
  this module makes zero delivery decisions itself.
- Transactional (ADR 0019): runs inside `recalls`' own publish
  transaction, in a savepoint. A recall that never actually commits
  enqueues no reminder.
- Ships its own system-level email template
  (`backend/templates/email/{locale}/recall_reminder.html`, en/es/fr/pt/ta)
  — no per-clinic setup step required.
- The template context is resolved in the message's locale (patient
  preference, else clinic communication language): `due_month` is a
  babel month name ("dezembro de 2026" for `pt-BR`), and `reason` is the
  label the recalls UI shows for the code ("Revisão de ortodontia", not
  `ortho_review`), from `reason_labels.py`. An unknown code is left out.
- The context also carries the clinic's `clinic_phone` and `clinic_address`,
  which the template's `tel:` "book" button and footer need (#1154).

## Data model

None. See `rr_0001`, a no-op migration on its own branch — required
only so `removable=True` has a self-contained branch to validate
against (`module_branch_is_isolated`).

## Constraints

Fires when the recall is *created* (often ~6 months before the actual
due date), not when it's *due* — wording reads as "we've scheduled
your next check-up for {month}" rather than "you're due" for that
reason. A `recall.due` event (the actual due-date reminder) is
reserved for a future cron-based follow-up.
