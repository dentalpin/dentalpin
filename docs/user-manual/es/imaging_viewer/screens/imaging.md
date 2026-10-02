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
last_verified_commit: ea31a0414010d1f18f1d46ebf7a10e97592b961f
screenshots: []
---

# Imagen

La página de imagen lista los estudios DICOM visibles de un paciente.
Elige un paciente en la cabecera (o abre `/imaging?patient_id=...`
desde la ficha del paciente); al seleccionar un estudio se muestra su
imagen con anotaciones encima. Mientras se resuelve el paciente, el
selector muestra carga; un id irresoluble dice "Paciente desconocido",
nunca un UUID. Las fechas salen en el idioma de la clínica y cada
botón de borrar anotación tiene nombre accesible. Al lanzar un escaneo
manual de la carpeta RVG se muestra un resumen (escaneados / nuevos /
autoaprobados / fallidos). La cola RVG tiene
pestañas por estado (pendientes / aprobadas / rechazadas / fallidas)
con conteos en vivo; las acciones solo se muestran en pendientes y las
fallidas muestran su error.

## Visor

La imagen se genera en el servidor (con ventana aplicada) desde el
archivo de la propia clínica. Si un estudio no se puede mostrar, la
página lo indica en lugar de mostrar una imagen rota.

Los estudios mostrados aquí son solo una ayuda visual — nunca un
diagnóstico.
