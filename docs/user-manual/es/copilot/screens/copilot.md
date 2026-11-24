---
module: copilot
screen: list
route: /copilot
related_endpoints:
  - GET /api/v1/copilot/sessions
  - GET /api/v1/copilot/sessions/{conversation_id}/messages
  - GET /api/v1/copilot/settings
  - PATCH /api/v1/copilot/settings
  - POST /api/v1/copilot/sessions
  - POST /api/v1/copilot/sessions/{conversation_id}/confirmations/{call_id}
  - POST /api/v1/copilot/sessions/{conversation_id}/end
  - POST /api/v1/copilot/sessions/{conversation_id}/messages
related_permissions:
  - copilot.chat
  - copilot.history.read
  - copilot.history.read_all
  - copilot.supervise
  - copilot.configure
related_paths:
  - backend/app/modules/copilot/frontend/pages/copilot/index.vue
last_verified_commit: da03135
---

# Copiloto (asistente de IA)

El copiloto es el asistente conversacional de DentalPin. Se abre desde
cualquier pantalla con el botón flotante o con `Cmd/Ctrl+K`, y tiene una
página propia en `/copilot` con el historial de conversaciones.

## Para qué sirve

Pídele en lenguaje natural lo que harías a mano en varias pantallas:

- **Pacientes** — buscar, resumir, crear y actualizar datos de contacto.
- **Agenda** — ver el día, buscar huecos libres, agendar, mover citas,
  cambiar su estado (confirmada, en gabinete, completada, no presentado)
  y cancelarlas.
- **Rellamadas** — listar las pendientes o vencidas del mes, registrar
  intentos de llamada, posponer o completar rellamadas.
- **Presupuestos** — listar por estado, ver el detalle y enviarlos al
  paciente por email.
- **Cobros y facturas** — registrar cobros con su reparto, consultar el
  historial de cobros de un paciente y consultar facturas (solo lectura).
- **Informes** — resumen de cobros, facturación y actividad de agenda.

## Flujos guiados (chips)

Al abrir una conversación vacía aparecen sugerencias agrupadas. Las tres
primeras encadenan varios pasos:

- **Briefing del día** — citas de hoy + rellamadas vencidas +
  presupuestos sin respuesta, en un solo resumen.
- **Preparar una visita** — ficha del paciente, su cita, rellamadas,
  presupuestos abiertos e historial de cobros en una pantalla.
- **Cubrir un hueco** — tras una cancelación propone pacientes de la
  lista de rellamadas (priorizando urgentes), agenda al elegido y
  registra el intento de llamada.

Solo ves los chips de las acciones que tu rol permite.

## Pendientes

La pestaña **Pendientes** reúne el trabajo abierto sobre el que puedes
actuar: rellamadas vencidas y presupuestos sin respuesta. Cada grupo
muestra hasta 20 filas. Si hay más, el grupo termina con "Mostrando 20
de N · Ver todos", que abre la lista completa ya filtrada (rellamadas
vencidas, o presupuestos en estado *enviado*).

## Confirmaciones

Toda acción que modifica datos (crear, mover, cancelar, cobrar, enviar)
se detiene y te muestra una tarjeta de confirmación antes de ejecutarse.
Las acciones irreversibles (cancelar cita, enviar presupuesto) se marcan
en rojo.

Cuando confirmas y la acción aparece como hecha, queda guardada. Si
después el copiloto no consigue escribir su respuesta (por ejemplo,
porque el proveedor de IA no responde a tiempo), verás un mensaje de
error, pero la acción sigue guardada; confirmar de nuevo no la repite.

## Briefing matinal por email

En **Ajustes → Integraciones → Copilot** puedes activar un email diario
automático ("Briefing del día") con las citas de hoy, las rellamadas
vencidas y los presupuestos sin respuesta. Eliges la hora de envío; el
destinatario es quien activa el interruptor. El briefing solo incluye
las secciones que tu rol puede ver.

## Permisos

El copiloto nunca ve ni hace nada que tu usuario no pueda hacer desde la
interfaz. Permisos del módulo: `copilot.chat` (usar el chat),
`copilot.history.read` (ver historial), `copilot.configure`
(proveedor/modelo/presupuesto).
