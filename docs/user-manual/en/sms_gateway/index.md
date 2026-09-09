---
module: sms_gateway
---

# SMS gateway

Text-message delivery for clinic notifications. One provider
configuration per clinic; messages queue through the standard
notification outbox with per-patient opt-out and a daily cap.

## Workflows

- **Configure**: Settings → Integrations → SMS gateway ([screen](./screens/settings.md)).
  Pick the `log` placeholder (records sends in the
  server log, sends nothing - clearly labelled "not sending") or a
  future provider with its credentials. Only admins.
- **Dry-run**: `/test` reports what would happen without sending.
- **Patients**: SMS follows the patient's phone number and their
  SMS opt-in; `do_not_contact` blocks everything.
