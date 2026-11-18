---
module: documents
screen: documents
route: /documents
last_verified_commit: 10085df
related_endpoints:
  - GET /api/v1/documents
  - POST /api/v1/documents
  - PATCH /api/v1/documents/{id}
  - DELETE /api/v1/documents/{id}
  - POST /api/v1/documents/generate
  - GET /api/v1/documents/{id}/download
  - GET /api/v1/documents/settings/letterhead
  - PUT /api/v1/documents/settings/letterhead
related_permissions:
  - documents.read
  - documents.write
related_paths:
  - backend/app/modules/documents/frontend/pages/documents/index.vue
  - backend/app/modules/documents/frontend/components/DocumentCreateModal.vue
  - backend/app/modules/documents/frontend/components/settings/DocumentsLetterheadPage.vue
---

# Documentos

Se encuentra en la entrada lateral **Documentos** (o desde la pestaña
del paciente). La lista muestra todos los documentos generados para
la clínica, ordenados por los más recientes.

## Qué puedes hacer

- **Filtrar** por tipo de documento (receta, certificado, derivación,
  solicitud de radiología) o estado (borrador, generado, archivado).
- **Crear** un nuevo documento — selecciona el paciente (con búsqueda
  en vivo contra el servidor), el tipo, el título y rellena los
  campos específicos de cada tipo.
- **Editar** el título o contenido de un documento (solo borradores).
- **Generar** — renderiza el documento como un PDF con la marca de
  agua de la clínica (nombre, logotipo, dirección, número de
  registro). Un documento generado aparece en la línea de tiempo del
  paciente. Las etiquetas del PDF y su título (*Carta de derivación*,
  *Certificado médico*, …) siguen el idioma en el que estés usando la
  aplicación — los diez, con el árabe maquetado de derecha a
  izquierda. El texto clínico que hayas escrito se reproduce tal cual;
  no se traduce.
- **Descargar** — guarda el PDF generado desde una fila con estado
  `generado`.
- **Archivar** (borrado suave) — oculta el documento de la lista
  activa pero conserva el registro para el histórico.

## Tipos de documento

| Tipo | Descripción |
|---|---|
| **Receta** | Medicamentos con dosis, frecuencia y duración |
| **Certificado médico** | Diagnóstico, descripción y período de validez |
| **Carta de derivación** | Profesional de destino, especialidad y resumen clínico |
| **Solicitud de radiología** | Tipo de examen, región y pregunta clínica |

## Membrete de la clínica

En **Ajustes → Facturación → Membrete de documentos** la clínica
puede sobrescribir la imagen que aparece en los PDF generados: nombre,
dirección, teléfono, correo, número de colegiado/registro y logotipo.
Los campos en blanco usan el perfil de la clínica.

## Quién puede usarlo

Los administradores y los dentistas pueden crear y generar documentos.
Los auxiliares tienen acceso de solo lectura. Otros roles necesitan
que se les conceda `documents.read` / `.write` explícitamente desde
la interfaz de administración de módulos. El editor de membrete
requiere `admin.clinic.write`.

## Consentimientos informados

Desde la ficha del paciente, crea o selecciona una plantilla de la clínica y genera el consentimiento. Abre el enlace en la tablet sin iniciar sesión del personal; caduca a los 30 minutos y admite una firma. El paciente o su representante indica su nombre y relación y dibuja su firma. Descarga el PDF firmado desde la ficha. Para revocar, genera un enlace de revocación y recoge una nueva firma; el consentimiento original se conserva. Las correcciones requieren un nuevo consentimiento.
