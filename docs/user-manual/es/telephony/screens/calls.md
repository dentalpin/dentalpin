---
module: telephony
screen: calls
route: /calls
related_endpoints:
  - GET /api/v1/telephony/calls
  - GET /api/v1/telephony/calls/active
  - PUT /api/v1/telephony/calls/{call_log_id}/note
related_permissions:
  - telephony.calls.read
  - telephony.calls.write
related_paths:
  - backend/app/modules/telephony/router.py
  - backend/app/modules/telephony/frontend/pages/calls/index.vue
last_verified_commit: f70d47ff
screenshots: []
---

# Registro de llamadas

El registro muestra todas las llamadas recibidas por la pasarela de
telefonía, vinculadas al paciente cuando exactamente una ficha tiene el
número del otro interlocutor: quien llama en una llamada entrante, el
número marcado en una saliente.

## Llamadas en curso

Las llamadas que están sonando o en curso aparecen como un aviso en la
parte superior de la página (y, si son entrantes, como notificación
emergente en cualquier pantalla para el personal con acceso a llamadas). **Abrir ficha** lleva
al paciente identificado; si el llamante es desconocido, **Buscar
paciente** abre el listado de pacientes filtrado por ese número.

## El listado

Cada fila muestra cuándo empezó la llamada, el llamante (con enlace a la
ficha si hay coincidencia), el número en formato internacional, el
estado (Sonando / Contestada / Finalizada / Perdida) y la duración. Se
puede filtrar por estado con el selector superior derecho. El personal
con permiso de escritura puede añadir una nota a la llamada desde la API
(el control en pantalla llegará con la integración de recalls).

## Requisitos

Un administrador debe configurar la pasarela en Ajustes → Integraciones
→ Telefonía (CTI): la centralita de la clínica o una automatización de
Zapier/Make envía los eventos de llamada a la URL de webhook de la
clínica, firmados con el secreto mostrado durante la configuración.
