---
module: prescriptions
screen: prescriptions
route: /prescriptions
last_verified_commit: c07d18a6d00fd5b4b17f801b64aa9bec0e31434a
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

- **Borradores** con líneas de texto libre (o desde una plantilla
  favorita). Los borradores se editan libremente.
- **Emitir** congela la receta (instantánea del prescriptor adjunta:
  nombre y licencia, sin firma);
  las correcciones son cancelar + reemitir, nunca ediciones.
- **Descargar** el PDF para imprimir. Sin envío por email en v1.
  El PDF sale en el idioma de la receta y marca BORRADOR/CANCELADA
  cuando corresponde.
- **Emitir** y **Anular** piden confirmación (son irreversibles).
- Tu **cédula profesional** se configura en Ajustes (sección
  clínica, identidad prescriptora) y queda impresa en el PDF.
- Atiende el aviso de alergias/interacciones — avisa, nunca bloquea.
