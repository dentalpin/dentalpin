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

# Bandeja de WhatsApp manual

Abre **WhatsApp manual**. Un administrador puede seleccionar este adaptador
desde la bandeja. La selección sustituye el adaptador de WhatsApp de la clínica.

1. Registra el consentimiento de WhatsApp del paciente en sus preferencias.
2. Usa **Enviar por WhatsApp** desde la ficha para escribir un mensaje, o
   **Enviar mensaje** desde la cita. El borrador aparece en la bandeja.
3. Pulsa **Abrir en WhatsApp** y envía allí el texto preparado.
4. Vuelve a DentalPin y pulsa **Marcar como enviado**. El envío aparece en
   el historial del paciente y DentalPin conserva quién lo declaró y cuándo.

Si se retira el consentimiento, cambia el teléfono o la cita se mueve,
se cancela o caduca, el borrador se bloquea. Usa **Descartar** si ya no
lo necesitas.
