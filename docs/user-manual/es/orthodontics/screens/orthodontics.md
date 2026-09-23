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
related_permissions:
  - orthodontics.cases.read
  - orthodontics.cases.write
  - orthodontics.controls.write
related_paths:
  - backend/app/modules/orthodontics/frontend/pages/orthodontics/index.vue
---

# Ortodoncia

La bandeja muestra los casos en cuatro vistas: activos, con control
vencido, sin próximo control y finalizados. Cada ficha muestra el
aparato "en boca ahora", el progreso "Mes X de ~N", la evolución de
fotos y el botón "+ Registrar control". El control se rellena con
chips (arcos por arcada, procedimientos, higiene) y propone el
próximo control en 3/4/6/8 semanas.
