---
module: notifications
screen: notifications
route: /settings/notifications
related_endpoints:
  - DELETE /api/v1/notifications/templates/{template_id}
  - GET /api/v1/notifications/logs
  - GET /api/v1/notifications/preferences/patient/{patient_id}
  - GET /api/v1/notifications/settings
  - GET /api/v1/notifications/smtp-settings
  - GET /api/v1/notifications/templates
  - GET /api/v1/notifications/templates/{template_id}
  - POST /api/v1/notifications/send
  - POST /api/v1/notifications/smtp-settings/test
  - POST /api/v1/notifications/templates
  - POST /api/v1/notifications/test
  - PUT /api/v1/notifications/preferences/patient/{patient_id}
  - PUT /api/v1/notifications/settings
  - PUT /api/v1/notifications/smtp-settings
  - PUT /api/v1/notifications/templates/{template_id}
related_permissions:
  - notifications.templates.read
  - notifications.templates.write
  - notifications.preferences.read
  - notifications.preferences.write
  - notifications.logs.read
  - notifications.send
  - notifications.settings.read
  - notifications.settings.write
related_paths:
  - backend/app/modules/notifications/frontend/pages/settings/notifications.vue
last_verified_commit: 0000000
---

# /settings/notifications

> _Esqueleto generado automáticamente — reemplazar con documentación real cuando se toque este módulo._

_Pantalla `/settings/notifications` del módulo `notifications`._

## Permisos

- `notifications.templates.read`
- `notifications.templates.write`
- `notifications.preferences.read`
- `notifications.preferences.write`
- `notifications.logs.read`
- `notifications.send`
- `notifications.settings.read`
- `notifications.settings.write`

## Para qué sirve

Configuración de notificaciones de la clínica.

### Canales (#287)

La tarjeta **Canales** decide por qué vía habla la clínica con los
pacientes:

- **Canal preferido** — Email o WhatsApp; todos los mensajes
  automáticos (confirmación de cita, recordatorio, bienvenida,
  presupuesto aceptado, …) salen primero por este canal. WhatsApp solo
  se puede elegir cuando la integración de Kapso está conectada.
- **Alternativa** — si el canal preferido no puede entregar (sin
  teléfono, sin plantilla de WhatsApp aprobada), se intenta el otro
  canal configurado en lugar de omitir en silencio.
- **Botones de envío** — qué botones de envío manual muestra el resto
  de la aplicación (cita, presupuesto, factura). Se requiere al menos
  uno.

### Tipos de mensaje

La tabla por tipo controla qué eventos notifican
(activado / envío automático / horas antes). Incluye factura enviada,
recordatorios de presupuesto (7/14 días) y recordatorios de revisión.

