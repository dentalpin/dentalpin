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

# Orthodontics

The inbox shows cases in four views: active, overdue control, no next
control, finished. Each sheet shows the "in mouth now" appliance,
"Month X of ~N" progress, photo evolution, and a "+ Register control"
button. Controls are filled with chips (wires per arch, procedures,
hygiene) and propose the next control in 3/4/6/8 weeks.
