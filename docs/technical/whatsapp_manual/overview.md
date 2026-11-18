---
module: whatsapp_manual
last_verified_commit: 0000000
---

# Manual WhatsApp overview

This optional module registers a clinic-selected WhatsApp adapter. The
notifications gateway prepares messages and the adapter returns `DEFERRED`.
Staff open a `wa.me` link, send in WhatsApp and declare the send in DentalPin.
The adapter performs no outbound network calls.

## Draft lifecycle

- Recorded WhatsApp consent is required. The adapter disables session
  replies and uses `Clinic.settings.country` to interpret local numbers.
- The patient action queues literal text. The appointment action remains
  in agenda's existing Send message menu. Appointment drafts keep the
  source appointment ID and the original start instant. Opening checks
  the clinic, patient, current appointment state and start time. Cancellation
  drafts require the appointment to remain cancelled. Other appointment
  drafts require an active appointment.
- The expiry job cancels pending drafts when their start instant has passed.
  Staff can also dismiss a pending draft from the tray.

## Delivery audit

The module's Alembic branch starts at `wam_0001`. Its table stores a
declaration per communication, with the clinic ID, staff user ID and declaration
time.
Erasing message content or contact details does not erase this declaration.
Notifications can read messages when the module is absent without querying
its table. Downgrading the optional module drops its declaration table
while the communication history remains in Notifications.
