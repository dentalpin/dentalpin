---
module: orthodontics
screen: orthodontics
route: /orthodontics
last_verified_commit: HEAD
related_endpoints:
  - GET /api/v1/orthodontics/cases
  - POST /api/v1/orthodontics/cases
  - GET /api/v1/orthodontics/cases/{case_id}
  - POST /api/v1/orthodontics/cases/{case_id}/status
  - POST /api/v1/orthodontics/cases/{case_id}/controls
  - GET /api/v1/orthodontics/cases/{case_id}/controls
  - POST /api/v1/orthodontics/cases/{case_id}/plan-link
  - POST /api/v1/orthodontics/cases/{case_id}/schedule
  - GET /api/v1/orthodontics/cases/{case_id}/installments
  - GET /api/v1/orthodontics/settings
  - PUT /api/v1/orthodontics/settings
related_permissions:
  - orthodontics.cases.read
  - orthodontics.cases.write
  - orthodontics.controls.write
related_paths:
  - backend/app/modules/orthodontics/frontend/pages/orthodontics/index.vue
---

# Ortodoncia

La bandeja lista cada caso con el nombre del paciente, en cuatro vistas: activos, con control
vencido, sin próximo control y finalizados. Cada ficha muestra el
aparato "en boca ahora", el progreso "Mes X de ~N", la evolución de
fotos y el botón "+ Registrar control". El control se rellena con
chips (arcos por arcada, procedimientos, higiene) y propone el
<próximo control en 3/4/6/8 semanas. El diálogo de estado solo ofrece
los movimientos legales según el estado actual (un caso finalizado
solo puede reabrirse a activo; un caso transferido no tiene
movimientos), y reabrir un caso finalizado conserva su fecha de
finalización. "Mes X" cuenta meses naturales desde la fecha de inicio
del caso, así que un paciente que llega a mitad de tratamiento puede
abrirse con una fecha de inicio pasada. Al crear un caso se indica su
fecha de inicio y, opcionalmente, el ortodoncista. Si el caso tiene un plan
vinculado, la ficha muestra las mensualidades (pagadas/pendientes):
"Generar mensualidades" crea cuota inicial + N cuotas en el plan, y
"Cobrar mensualidad" abre los cobros del paciente, donde se registra
el pago del mes. Cada control puede guardar su próximo control como
recordatorio automático.
