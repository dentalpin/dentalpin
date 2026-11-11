---
module: imaging_viewer
screen: imaging
route: /imaging
related_endpoints:
  - GET /api/v1/imaging_viewer/patients/{patient_id}/studies
  - GET /api/v1/imaging_viewer/studies/{study_id}
  - GET /api/v1/imaging_viewer/studies/{study_id}/render
  - POST /api/v1/imaging_viewer/rvg/imports/approve-batch
related_permissions:
  - imaging_viewer.studies.read
  - imaging_viewer.rvg.write
related_paths:
  - backend/app/modules/imaging_viewer/router.py
  - backend/app/modules/imaging_viewer/frontend/pages/imaging/index.vue
last_verified_commit: 6a661916db4e15d4deeb4e23a03132e49a3ec913
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
fallidas muestran su error. Las filas pendientes tienen casillas de
selección con un control de seleccionar todo, y dos acciones por
lote que reflejan los botones de fila: aprobar la selección por la
sugerencia de cada fila, o aprobar la selección para el paciente
elegido en la cabecera. El lote se ejecuta fila a fila: una fila ya
decidida o con archivo fuente ausente se reporta por su nombre
mientras las aprobadas se mantienen, y un aviso indica cuántas se
aprobaron. Debajo de la cola de
importación se listan las identidades de sensor vinculadas con el nombre
del paciente, con acción para desvincular un emparejamiento DICOM erróneo.

## Visor

La imagen se genera en el servidor (con ventana aplicada) desde el
archivo de la propia clínica. Si un estudio no se puede mostrar, la
página lo indica en lugar de mostrar una imagen rota.

Los estudios mostrados aquí son solo una ayuda visual — nunca un
diagnóstico.
