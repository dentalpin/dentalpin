---
module: sms_gateway
last_verified_commit: 0f333000
---

# sms_gateway — events

No events of its own. Sends flow through the standard notification
lifecycle with `channel=sms` (payload: `clinic_id`, `patient_id`,
`message_id`, `channel`, `template_key`, `subject`, `status`,
`error_message`, `occurred_at`):

| Event | When |
|---|---|
| `notification.queued` | SMS accepted into the outbox |
| `notification.sent` | placeholder recorded the send |
| `notification.failed` | no config / unimplemented provider |
| `notification.delivered` | provider delivery receipt |

Inbound SMS replies arrive with the provider backend (future
`record_inbound_reply` wiring toward the patient timeline).
