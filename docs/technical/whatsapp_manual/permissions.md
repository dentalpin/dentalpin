---
module: whatsapp_manual
last_verified_commit: 0000000
---

# Manual WhatsApp permissions

| Permission | Gates | Endpoints |
| --- | --- | --- |
| `whatsapp_manual.read` | Read the clinic tray, badge count and adapter selection | GET `/tray`, `/count`, `/settings` |
| `whatsapp_manual.write` | Open, declare sending, dismiss or draft | POST `/tray/{id}/open`, `/tray/actions`, `/drafts` |
| `whatsapp_manual.settings.write` | Select the clinic adapter | PUT `/settings` |

Routes use the `/api/v1/whatsapp_manual` prefix and the active clinic.
Draft creation also requires `patients.read`. Admins have all three permissions.
Dentists, hygienists, assistants and receptionists have read and write.
