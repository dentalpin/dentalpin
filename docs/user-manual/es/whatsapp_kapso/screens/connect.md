---
module: whatsapp_kapso
screen: connect
route: /settings/integrations/whatsapp-kapso
related_endpoints:
  - GET /api/v1/whatsapp_kapso/settings
  - PUT /api/v1/whatsapp_kapso/settings
  - POST /api/v1/whatsapp_kapso/templates/sync
  - POST /api/v1/whatsapp_kapso/templates/map
  - POST /api/v1/whatsapp_kapso/test
last_verified_commit: f70d47ff
---

# Conectar WhatsApp (Kapso)

Página en **Ajustes → Integraciones → WhatsApp (Kapso)** (solo administradores).

## Pasos

1. **Credenciales.** Pega la *API key* de Kapso, el *Phone number ID* y el
   *Business account ID* de tu número conectado, y el *secret del webhook*.
   Guarda. Las claves se almacenan cifradas y nunca se vuelven a mostrar. Un
   *Phone number ID* que otra clínica ya tiene conectado se rechaza: si el
   guardado falla, revísalo.
2. **Webhook.** Copia la URL del webhook que muestra la página y pégala en la
   configuración de webhooks de tu proyecto de Kapso. Así DentalPin recibe los
   estados de entrega y las respuestas de los pacientes.
3. **Plantillas.** Pulsa *Sincronizar* para traer tus plantillas aprobadas de
   Meta. Luego asocia cada tipo de notificación (p. ej. "recordatorio de cita")
   a una plantilla aprobada.
4. **Prueba.** Envía un mensaje de prueba a un número para verificar la conexión.

## Responder a un paciente

Cuando un paciente escribe por WhatsApp, su mensaje aparece en el **timeline** y
en la tarjeta de conversación de su ficha. Puedes responder en texto libre
dentro de las 24h siguientes; pasado ese plazo, debes usar una plantilla.
