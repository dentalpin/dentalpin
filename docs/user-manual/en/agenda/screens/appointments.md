---
module: agenda
screen: list
route: /appointments
related_endpoints:
  - DELETE /api/v1/agenda/appointments/{appointment_id}
  - DELETE /api/v1/agenda/cabinets/{cabinet_id}
  - GET /api/v1/agenda/appointments
  - GET /api/v1/agenda/appointments/{appointment_id}
  - GET /api/v1/agenda/appointments/{appointment_id}/cabinet-history
  - GET /api/v1/agenda/appointments/{appointment_id}/transitions
  - GET /api/v1/agenda/cabinets
  - GET /api/v1/agenda/kanban/day
  - PATCH /api/v1/agenda/appointment-treatments/{appointment_treatment_id}
  - PATCH /api/v1/agenda/appointments/{appointment_id}/cabinet
  - POST /api/v1/agenda/appointments
  - POST /api/v1/agenda/appointments/{appointment_id}/transitions
  - POST /api/v1/agenda/cabinets
  - PUT /api/v1/agenda/appointments/{appointment_id}
  - PUT /api/v1/agenda/cabinets/{cabinet_id}
related_permissions:
  - agenda.appointments.read
  - agenda.appointments.write
  - agenda.cabinets.read
  - agenda.cabinets.write
related_paths:
  - backend/app/modules/agenda/frontend/pages/appointments/index.vue
  - backend/app/modules/agenda/router.py
last_verified_commit: 0cce028b
---

# Appointments

The clinic's operational calendar. Browse the week or the day,
create appointments by dragging on free slots, move them between
professionals and rooms, and walk them through their workflow
(scheduled → confirmed → in-room → completed → billed).

## At a glance

- **Four views** — weekly, daily, and kanban on desktop; a simplified
  one-day mobile view on small screens. The view selector lives in
  the header, except on mobile where only the daily view exists.
- **Cabinet and professional filters** — chips above the calendar.
  Appointments with no room assigned are **always** visible so the
  front desk can drag them onto the right room.
- **Drag, resize, and across-day moves** — drag a card to a different
  hour or professional to move it; drag the lower edge to change its
  duration. If it overlaps with another appointment for the same
  professional or room a warning toast appears, but the operation is
  still saved.
- **Backend conflicts** — if the server rejects a placement (HTTP 409)
  the calendar refreshes and shows an error toast; the appointment
  snaps back to its previous slot.
- **Daily kanban** — appointments group by status (scheduled,
  confirmed, in-room…). Lets the clinical team see at a glance what
  is coming next.

## Create an appointment

> Requires `agenda.appointments.write`.

1. On the weekly or daily view, click or drag on a free slot. On
   kanban or mobile, tap **New appointment** or the floating button.
2. Pick the patient, reason, and duration. The professional and the
   room are pre-selected based on the slot you opened the modal from.
3. **Save**. The `appointment.scheduled` event is published so
   sibling modules (like notifications) can send the confirmation.

### Linking treatments from a plan

Once a patient is selected, the modal offers the pending treatments
from their treatment plans, so the visit is booked against real
planned work instead of a free-text reason.

- Plans in **draft**, **awaiting acceptance** and **accepted** all
  offer their treatments. A treatment already done, or one from a
  completed or closed plan, is not offered.
- Treatments coming from a plan whose quote the patient has not
  accepted yet carry a **Quote awaiting acceptance** badge (hourglass
  icon), in both the picker and the selected list. Booking them is
  allowed on purpose — clinics routinely schedule the first visit
  while the patient is still deciding — the badge is there so
  reception knows it is booking ahead of the acceptance.
- The treatment can only be marked as **performed** once the quote is
  accepted and the plan is active; that is where the money is booked.
- If the patient has no plan with pending treatments, the selector
  explains so instead of showing an empty picker.

## Move or resize

> Requires `agenda.appointments.write`.

1. Drag the card to a different time, day, or professional to move it.
2. Drag the lower edge to change the duration.
3. If the new position overlaps another appointment with the same
   professional or room you'll see a yellow warning, but the change is
   saved. If the backend rejects it (HTTP 409 for a stricter
   collision), the view refreshes and the card returns to its
   original slot.

## Advance the status

> Requires `agenda.appointments.write`.

1. Open the appointment by clicking on it.
2. In the **Quick actions** panel pick the next available transition:
   *Confirm*, *In-room*, *Complete*, *Cancel*.
3. When transitioning to **completed** a follow-up modal appears with
   actions contributed by sibling modules (e.g. *Schedule recall*).
   The modal stays hidden when no module contributes to it.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View the calendar, open appointments, see room history | `agenda.appointments.read` |
| Create, move, resize, cancel, transition | `agenda.appointments.write` |
| See clinic rooms (filter chips) | `agenda.cabinets.read` |
| Edit a visit's clinical note | `clinical_notes.notes.write` |

## Troubleshooting

- **"New appointment" button is missing.** Your role lacks
  `agenda.appointments.write`.
- **No professionals show up in the filter.** No clinic members with
  an active clinical role exist yet. Create or activate professionals
  under *Settings → Users*.
- **A moved appointment snaps back.** The backend rejected the change
  with HTTP 409 (typically because the professional or room already
  has another appointment in that slot). Check the error toast and
  try a different time.
- **The calendar only runs 08:00–21:00.** The `schedules` module is
  not installed or has no schedule configured; the agenda falls back
  to its default window.
