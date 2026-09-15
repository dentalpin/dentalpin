---
module: prescriptions
screen: prescriptions
route: /prescriptions
last_verified_commit: HEAD
related_endpoints:
  - GET /api/v1/prescriptions/patients/{patient_id}/prescriptions
  - POST /api/v1/prescriptions/patients/{patient_id}/prescriptions
  - PATCH /api/v1/prescriptions/prescriptions/{prescription_id}
  - POST /api/v1/prescriptions/prescriptions/{prescription_id}/issue
  - POST /api/v1/prescriptions/prescriptions/{prescription_id}/cancel
  - GET /api/v1/prescriptions/prescriptions/{prescription_id}/pdf
related_permissions:
  - prescriptions.read
  - prescriptions.write
  - prescriptions.issue
related_paths:
  - backend/app/modules/prescriptions/frontend/pages/prescriptions/index.vue
---

# Recetas

Abre con un paciente seleccionado para ver sus recetas, o crea un
borrador desde la ficha del paciente (acción "Nueva receta").

## Qué puedes hacer

- **Borradores** con líneas de texto libre (o desde catálogo /
  plantilla favorita). Los borradores se editan libremente.
- **Emitir** congela la receta (firma del prescriptor incluida);
  las correcciones son cancelar + reemitir, nunca ediciones.
- **Descargar** el PDF para imprimir. Sin envío por email en v1.
- Atiende el aviso de alergias/interacciones — avisa, nunca bloquea.
