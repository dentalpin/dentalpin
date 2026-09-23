---
module: imaging_ai
screen: ai-jobs
route: /imaging-ai
related_endpoints:
  - GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - GET /api/v1/imaging_ai/ai-jobs/{job_id}
related_permissions:
  - imaging_ai.jobs.read
related_paths:
  - backend/app/modules/imaging_ai/router.py
  - backend/app/modules/imaging_ai/frontend/pages/imaging-ai/index.vue
last_verified_commit: 1b7995366fee99533f24c738823708168bf4aedb
screenshots: []
---

# Trabajos de IA

La página de trabajos de IA lista los análisis de segmentación de un
paciente con su estado: en cola, en curso, terminado, fallido o cancelado.

## Cómo abrir la página

Abre `/imaging-ai?patient_id=<uuid>` — por ejemplo desde la ficha del
paciente. Sin un paciente seleccionado, la página explica cómo abrirla.

## Resultados

Los análisis terminados vinculan sus documentos superpuestos al estudio
de origen. La salida de la IA es solo una ayuda visual — nunca un
diagnóstico.
