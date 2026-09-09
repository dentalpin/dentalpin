---
module: sms_gateway
screen: settings
route: /settings/integrations/sms-gateway
last_verified_commit: 0b59a2a2
related_endpoints:
  - GET /api/v1/sms_gateway/settings
  - PUT /api/v1/sms_gateway/settings
  - GET /api/v1/sms_gateway/providers
  - POST /api/v1/sms_gateway/test
related_permissions:
  - sms_gateway.settings.read
  - sms_gateway.settings.write
related_paths:
  - backend/app/modules/sms_gateway/frontend/components/SmsGatewaySettingsPage.vue
---

# Pasarela SMS

En **Ajustes → Integraciones → SMS** (solo admin). Una configuración
de proveedor por clínica; sin fila activa guardada, el SMS sigue no
disponible en todas partes.

## Qué puedes hacer

- **Elegir el proveedor** entre los backends realmente registrados
  (v1 solo trae el marcador `log`). Los nombres desconocidos se
  rechazan con 422 — un backend sin implementar nunca queda
  seleccionado.
- **Fijar el número remitente** y **activar** el proveedor.
- **Probar**: comprobación en seco que informa de lo que PASARÍA sin
  enviar nada. El proveedor incluido registra los mensajes en el log
  del servidor en vez de enviarlos — no lo instales pensando que los
  SMS salen hasta tener un backend real.
