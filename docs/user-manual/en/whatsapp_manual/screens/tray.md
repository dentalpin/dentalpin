---
module: whatsapp_manual
screen: tray
route: /whatsapp-manual
related_endpoints:
  - GET /api/v1/whatsapp_manual/tray
  - POST /api/v1/whatsapp_manual/tray/{message_id}/open
  - POST /api/v1/whatsapp_manual/tray/actions
  - POST /api/v1/whatsapp_manual/drafts
  - PUT /api/v1/whatsapp_manual/settings
last_verified_commit: 0000000
---

# Manual WhatsApp tray

Open **Manual WhatsApp**. A clinic admin can select this adapter from the
tray. That selection replaces the current WhatsApp adapter for the clinic.

1. Record the patient's WhatsApp consent in their notification preferences.
2. Use **Send by WhatsApp** on the patient record for a new message, or use
   **Send message** from the appointment. The draft appears in the tray.
3. Select **Open in WhatsApp** and send the prepared text there.
4. Return to DentalPin and select **Mark as sent**. The patient history
   records the send, and DentalPin retains who declared it and when.

A draft cannot open if consent is withdrawn, the phone number changes or
the appointment has been moved, cancelled or has expired. Use **Dismiss**
for drafts you no longer need.
