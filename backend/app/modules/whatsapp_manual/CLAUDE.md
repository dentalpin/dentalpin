# Manual WhatsApp

Optional community module for staff-operated WhatsApp delivery. It depends on
`notifications`, `patients`, and `agenda`. It registers its adapter and expiry
job on activation and owns an Alembic branch and the declaration table.

## Public API

Routes under `/api/v1/whatsapp_manual`.

| Route | Permission | Purpose |
| --- | --- | --- |
| GET `/tray`, `/count`, `/settings` | `whatsapp_manual.read` | Read the clinic tray, count or adapter selection |
| PUT `/settings` | `whatsapp_manual.settings.write` | Select or remove the manual adapter for the clinic |
| POST `/tray/{id}/open` | `whatsapp_manual.write` | Revalidate consent, appointment and phone before returning a WhatsApp link |
| POST `/tray/actions` | `whatsapp_manual.write` | Declare sending or dismiss pending drafts |
| POST `/drafts` | `whatsapp_manual.write`, `patients.read` | Enqueue a staff message |

## Setup and data

Select the manual adapter on the tray as a clinic admin. Use the existing
Notifications settings to pick WhatsApp as the preferred automatic channel.
Edit templates in Settings → Notifications → Templates or use the
Notifications template API. For each event
and patient language, supply `channel=whatsapp` and a plain-text `body_text`
with the event's Jinja variables, for example `{{ patient_name }}` and
`{{ appointment_date }}` for reminders (printed on the clinic's clock in the
message locale's date order). The adapter uses the clinic template
then the gateway's system-template fallback for that locale. Staff drafts
carry literal text. The patient button uses `patient.summary.actions`.
Appointment notifications use the existing agenda menu.
Missing or invalid text is recorded as skipped.

Record affirmative WhatsApp consent on the patient's communications
preferences card. The adapter requires the existing consent timestamp.
International mobile numbers are stored in E.164. Local numbers are
interpreted using `Clinic.settings.country`.

## Lifecycle and events

Opening a draft checks the appointment ID, patient, status and original
start instant. Cancellation drafts require a cancelled appointment. Other
appointment drafts require an active appointment. The expiry job cancels
drafts starting in the past.
A staff declaration stores the clinic ID, user ID and time in
`whatsapp_manual_delivery_declarations`, on the module's own Alembic branch.
Its communication transitions to sent and publishes `notification.sent`
once through the notifications gateway after commit. Erasure clears the
message context and preserves the declaration. Repeated declarations leave
the audit intact. Uninstall skips pending manual drafts and removes adapter selection and the
module's declaration table. Notification rows remain in the core history.
