---
module: recalls
screen: list
route: /recalls
related_endpoints:
  - DELETE /api/v1/recalls/{recall_id}
  - GET /api/v1/recalls
  - GET /api/v1/recalls/export.csv
  - GET /api/v1/recalls/patients/{patient_id}
  - GET /api/v1/recalls/settings
  - GET /api/v1/recalls/stats/dashboard
  - GET /api/v1/recalls/suggestions/next
  - GET /api/v1/recalls/{recall_id}
  - GET /api/v1/recalls/{recall_id}/attempts
  - PATCH /api/v1/recalls/{recall_id}
  - POST /api/v1/recalls
  - POST /api/v1/recalls/{recall_id}/attempts
  - POST /api/v1/recalls/{recall_id}/cancel
  - POST /api/v1/recalls/{recall_id}/done
  - POST /api/v1/recalls/{recall_id}/link-appointment
  - POST /api/v1/recalls/{recall_id}/snooze
  - PUT /api/v1/recalls/settings
related_permissions:
  - recalls.read
  - recalls.write
  - recalls.delete
related_paths:
  - backend/app/modules/recalls/frontend/pages/recalls/index.vue
  - backend/app/modules/recalls/router.py
last_verified_commit: b40a1d2
---

# Call list

Monthly queue of patients to contact. Each row is a recall — who to
call, why, when it's due, and what state it's in. Designed for the
front desk to work top-down: press **Call**, log the attempt, and
move the recall to its next state.

## At a glance

- **Month filter** — defaults to the current month. The queue shows
  recalls whose `due_month` falls inside the selected month.
- **Four counters at the top** — *Due this week*, *Overdue*,
  *Scheduled this month*, *Conversion rate*. They recompute as
  filters change. Conversion is scheduled appointments / overdue
  recalls for the month. *Due this week* counts open recalls with an
  exact due date in the current Monday-to-Sunday week (clinic time);
  month-only recalls count under the month, not the week.
- **Extra filters** — reason, status, priority, plus an *Overdue*
  toggle. Filter state lives in the URL so links are shareable.
- **Default status:** *pending*. *Done*, *cancelled*, and *needs
  review* rows only appear when you switch the status filter.
- **Automatic exclusions:** archived patients or patients with
  `do_not_contact = true` are kept out of the active queue; their
  recalls land in the **Needs review** bucket.
- **CSV export** — header button. Honors the active filters.

## Work a recall

> Requires `recalls.write`.

1. Click **Call** on the row. A small popover opens with the patient
   phones and the outcome buttons.
2. Pick the outcome: *No answer*, *Scheduled*, *Declined*, *Done*.
   Each one logs an attempt and moves the recall to the matching
   state.
3. If the patient accepts an appointment, click **Schedule
   appointment** on the row. The agenda opens with the patient
   pre-selected; on save the recall is linked automatically and
   moves to *contacted/scheduled*.

## Snooze or close

> Requires `recalls.write`.

1. Use the **⋮** row menu for ad-hoc actions:
   - **Snooze N months** — pushes `due_month` and keeps the recall
     pending. Publishes `recall.snoozed`.
   - **Done** — marks the recall as completed. Publishes
     `recall.completed`.
   - **Cancel** — drops the recall from the active queue. Publishes
     `recall.cancelled`.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View list, counters, CSV | `recalls.read` |
| Call, snooze, complete, link an appointment | `recalls.write` |
| Edit settings (reason intervals, category map) | `recalls.write` |
| Delete a recall | `recalls.delete` (admin only by default) |

## Troubleshooting

- **A patient with an already-booked appointment is still pending.**
  Auto-link only fires when **exactly one** active recall matches. If
  two or more match, link it manually with **Schedule appointment**
  on the row.
- **A patient is missing from the queue.** Check whether the patient
  is archived or flagged *Do not contact* on their record — in either
  case the recall has moved to **Needs review** (status filter).
- **Conversion shows zero.** Either the selected month has no overdue
  recalls yet, or none of them have been scheduled.
