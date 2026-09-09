---
module: sms_gateway
---

# Pasarela SMS

Envío de mensajes de texto para notificaciones. Una configuración por
clínica; los mensajes pasan por la cola estándar con exclusión por
paciente y límite diario.

## Flujos

- **Configurar**: Ajustes → Integraciones → SMS ([pantalla](./screens/settings.md)).
  Elige el marcador `log` (registra envíos en el log,
  no envía nada - marcado "not sending") o un futuro proveedor con
  sus credenciales. Solo administradores.
- **Probar**: `/test` informa de lo que pasaría sin enviar.
- **Pacientes**: el SMS sigue el teléfono del paciente y su
  aceptación; `do_not_contact` lo bloquea todo.
