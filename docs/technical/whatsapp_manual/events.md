---
module: whatsapp_manual
last_verified_commit: 0000000
---

# Manual WhatsApp events

| Event | When | Effect |
| --- | --- | --- |
| `notification.sent` | A staff declaration moves a draft to sent and commits | The notifications gateway publishes the existing event. Patient Timeline records the communication. |

Opening or dismissing drafts does not publish a sent event. Repeating a
successful declaration reuses the current status and leaves the original
actor and timestamp intact. The event records the staff declaration and
carries no delivery receipt from WhatsApp.

The module does not subscribe to events. Its expiry job checks pending
appointment drafts every five minutes.
