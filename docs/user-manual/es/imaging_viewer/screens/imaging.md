---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/render
related_permissions:
  - imaging_viewer.studies.read
related_paths:
  - backend/app/modules/imaging_viewer/router.py
  - backend/app/modules/imaging_viewer/frontend/pages/imaging/index.vue
last_verified_commit: a118a7ecd5043b8e861eb77ed3be1bb874ca91b2
screenshots: []
---

# Imagen

La página de imagen lista los estudios DICOM visibles de un paciente.
Elige un paciente en la cabecera (o abre `/imaging?patient_id=...`
desde la ficha del paciente); al seleccionar un estudio se muestra su
imagen con anotaciones encima.

## Visor

La imagen se genera en el servidor (con ventana aplicada) desde el
archivo de la propia clínica. Si un estudio no se puede mostrar, la
página lo indica en lugar de mostrar una imagen rota.

Los estudios mostrados aquí son solo una ayuda visual — nunca un
diagnóstico.
