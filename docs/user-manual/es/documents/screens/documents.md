---
module: documents
screen: documents
route: /documents
related_endpoints:
  - GET /api/v1/documents
  - POST /api/v1/documents
  - PATCH /api/v1/documents/{id}
  - DELETE /api/v1/documents/{id}
  - POST /api/v1/documents/generate
related_permissions:
  - documents.read
  - documents.write
related_paths:
  - backend/app/modules/documents/frontend/pages/documents/index.vue
---

# Documentos

Se encuentra en la entrada lateral **Documentos** (o desde la pestaña
del paciente). La lista muestra todos los documentos generados para
la clínica, ordenados por los más recientes.

## Qué puedes hacer

- **Buscar** por título del documento (en vivo, con retardo).
- **Filtrar** por tipo de documento (receta, certificado, derivación,
  solicitud de radiología) o estado (borrador, generado, archivado).
- **Crear** un nuevo documento — selecciona el paciente, el tipo, el
  título y rellena los campos específicos de cada tipo.
- **Editar** el título o contenido de un documento (solo borradores).
- **Generar** — renderiza el documento como un PDF con la marca de
  agua de la clínica (nombre, logotipo, dirección, número de
  registro). Un documento generado aparece en la línea de tiempo del
  paciente.
- **Archivar** (borrado suave) — oculta el documento de la lista
  activa pero conserva el registro para el histórico.

## Tipos de documento

| Tipo | Descripción |
|---|---|
| **Receta** | Medicamentos con dosis, frecuencia y duración |
| **Certificado médico** | Diagnóstico, descripción y período de validez |
| **Carta de derivación** | Profesional de destino, especialidad y resumen clínico |
| **Solicitud de radiología** | Tipo de examen, región y pregunta clínica |

## Quién puede usarlo

Los administradores y los dentistas pueden crear y generar documentos.
Los auxiliares tienen acceso de solo lectura. Otros roles necesitan
que se les conceda `documents.read` / `.write` explícitamente desde
la interfaz de administración de módulos.
