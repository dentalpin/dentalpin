---
module: imaging_ai
screen: ai-jobs
route: /imaging-ai
related_endpoints:
  - POST /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - POST /api/v1/imaging_ai/ai-jobs/{job_id}/confirm
  - GET /api/v1/imaging_ai/patients/{patient_id}/ai-jobs
  - GET /api/v1/imaging_ai/patients/{patient_id}/dicom-documents
  - GET /api/v1/imaging_ai/ai-jobs/{job_id}
  - DELETE /api/v1/imaging_ai/ai-jobs/{job_id}
related_permissions:
  - imaging_ai.jobs.read
  - imaging_ai.jobs.write
related_paths:
  - backend/app/modules/imaging_ai/router.py
  - backend/app/modules/imaging_ai/frontend/pages/imaging-ai/index.vue
last_verified_commit: ad339611ade2847809b6478a60a7a1354990b432
screenshots: []
---

# Trabajos de IA

La página de trabajos de IA cubre el flujo completo: elegir paciente,
elegir los archivos DICOM (el primero marcado es el documento principal;
marca el resto de la serie para análisis volumétricos nnU-Net), elegir
el motor (pano para imágenes únicas, nnU-Net para volúmenes de serie) y
lanzar el análisis. Los trabajos se listan con su estado — propuesto, en
cola, en curso, terminado, fallido, cancelado — además de errores y el
final del registro del motor.

## Cómo abrir la página

Abre `/imaging-ai` y busca el paciente, o usa el enlace directo
`/imaging-ai?patient_id=<uuid>` desde la ficha del paciente. Sin permiso
de lectura de pacientes, solo funciona el enlace directo.

## Borradores y revisión

Los análisis terminados guardan sus superposiciones como borradores de
IA — nunca como radiografías de la galería ni vinculados al original.
Revisa la superposición y Confirma: los trabajos propuestos empiezan a
ejecutarse y los borradores terminados quedan marcados como revisados.
Nada de lo que produce el modelo entra en la historia clínica sin ese
paso explícito. La salida de la IA es solo una ayuda visual — nunca un
diagnóstico.
