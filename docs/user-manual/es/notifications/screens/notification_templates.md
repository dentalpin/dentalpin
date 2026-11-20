---
module: notifications
screen: notification_templates
route: /settings/communications/templates
related_endpoints:
  - GET /api/v1/notifications/templates/editor/{template_key}
  - POST /api/v1/notifications/templates/editor/{template_key}/preview
  - PUT /api/v1/notifications/templates/editor/{template_key}
  - DELETE /api/v1/notifications/templates/editor/{template_key}
related_permissions:
  - notifications.templates.read
  - notifications.templates.write
related_paths:
  - backend/app/modules/notifications/frontend/components/settings/NotificationTemplatesPage.vue
last_verified_commit: 0000000
screenshots:
  - notifications/notification-templates-email.png
  - notifications/notification-templates-whatsapp.png
---

# Plantillas de notificaciones

Abre **Ajustes → Notificaciones → Plantillas**. Selecciona el tipo de
mensaje, el canal y el idioma de la plantilla. El estado indica si esa
variante usa un texto de la clínica, un texto por defecto o si carece de
texto de sistema.

- **Correo electrónico** permite editar el asunto, el cuerpo HTML y un
  texto sin formato opcional.
- **WhatsApp** permite editar texto sin formato cuando la clínica usa el
  adaptador manual. Las plantillas aprobadas se gestionan en los ajustes
  del proveedor.
- **SMS y Push web** muestran el texto en modo de solo lectura.

Pulsa una variable para insertarla en el último campo seleccionado. Puedes
omitir los valores opcionales en la vista previa para comprobar cómo queda el
mensaje cuando faltan datos. La vista previa usa ejemplos ficticios. Guarda
cuando el texto esté listo. Los errores de sintaxis y de variables aparecen
junto al campo correspondiente.

Para quitar un texto de la clínica, pulsa **Volver al texto por defecto**
y confirma. Los mapeos del proveedor se conservan. Una variante de WhatsApp
marcada **Sin texto de sistema** queda sin plantilla al retirar el texto de
la clínica. Los borradores ya preparados conservan su texto.

## Permisos

- `notifications.templates.read` permite consultar y previsualizar.
- `notifications.templates.write` permite guardar y restaurar.
