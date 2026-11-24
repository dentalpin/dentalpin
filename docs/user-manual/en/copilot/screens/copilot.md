---
module: copilot
screen: list
route: /copilot
related_endpoints:
  - GET /api/v1/copilot/sessions
  - GET /api/v1/copilot/sessions/{conversation_id}/messages
  - GET /api/v1/copilot/settings
  - PATCH /api/v1/copilot/settings
  - POST /api/v1/copilot/sessions
  - POST /api/v1/copilot/sessions/{conversation_id}/confirmations/{call_id}
  - POST /api/v1/copilot/sessions/{conversation_id}/end
  - POST /api/v1/copilot/sessions/{conversation_id}/messages
related_permissions:
  - copilot.chat
  - copilot.history.read
  - copilot.history.read_all
  - copilot.supervise
  - copilot.configure
related_paths:
  - backend/app/modules/copilot/frontend/pages/copilot/index.vue
last_verified_commit: da03135
---

# Copilot (AI assistant)

The copilot is DentalPin's conversational assistant. Open it from any
screen with the floating button or `Cmd/Ctrl+K`; it also has its own
page at `/copilot` with the conversation history.

## What it's for

Ask in natural language for what you'd otherwise do across screens:

- **Patients** — search, summarize, create and update contact data.
- **Schedule** — see the day, find free slots, book, reschedule, change
  appointment status (confirmed, in treatment, completed, no-show) and
  cancel.
- **Recalls** — list this month's due or overdue recalls, log call
  attempts, snooze or complete recalls.
- **Budgets** — list by status, view detail and send them to the
  patient by email.
- **Payments & invoices** — record payments with their allocation,
  check a patient's payment history and view invoices (read only).
- **Reports** — collections, billing and scheduling summaries.

## Guided workflows (chips)

An empty conversation shows grouped suggestions. The first three chain
several steps:

- **Daily briefing** — today's appointments + overdue recalls +
  unanswered budgets in one summary.
- **Prepare a visit** — patient record, their appointment, recalls,
  open budgets and payment history on one screen.
- **Fill a gap** — after a cancellation it suggests patients from the
  recall list (urgent first), books the chosen one and logs the call
  attempt.

You only see chips for actions your role allows.

## To do (Pendientes)

The **To do** tab lists open work you can act on: overdue recalls and
budgets awaiting a response. Each group shows up to 20 rows. When there
are more, the group ends with "Showing 20 of N · See all", which opens
the full, filtered list (overdue recalls, or budgets with status
*sent*).

## Confirmations

Every action that modifies data (create, move, cancel, charge, send)
pauses and shows you a confirmation card before executing. Irreversible
actions (cancel appointment, send budget) are highlighted in red.

Once you confirm and the action shows as done, it is saved. If the
copilot then fails to write its reply (for example the AI provider
times out), you see an error message, but the action stays saved;
confirming again does not repeat it.

## Morning briefing email

In **Settings → Integrations → Copilot** you can enable an automatic
daily email ("Daily briefing") with today's appointments, overdue
recalls and unanswered budgets. You pick the send hour; the recipient
is whoever flips the switch. The briefing only includes the sections
your role can see.

## Permissions

The copilot never sees or does anything your user couldn't do through
the UI. Module permissions: `copilot.chat` (use the chat),
`copilot.history.read` (view history), `copilot.configure`
(provider/model/budget).
