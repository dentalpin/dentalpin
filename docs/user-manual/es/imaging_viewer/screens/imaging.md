---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/frame
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
Al seleccionar un estudio se abre en el visor integrado.

## Cómo abrir la página

Abre `/imaging?patient_id=<uuid>` — por ejemplo desde la ficha del
paciente. Sin un paciente seleccionado, la página explica cómo abrirla.

## Visor

El visor muestra el estudio desde el archivo de la propia clínica. Si el
visor interactivo no puede cargarse, la página ofrece descargar el
archivo DICOM original.

Los estudios mostrados aquí son solo una ayuda visual — nunca un
diagnóstico.
