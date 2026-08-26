---
module: medication_catalog
screen: clinical-medications
route: /settings/clinical/medications
related_endpoints:
  - GET /api/v1/medication_catalog
  - POST /api/v1/medication_catalog
  - PATCH /api/v1/medication_catalog/{id}
  - DELETE /api/v1/medication_catalog/{id}
  - POST /api/v1/medication_catalog/seed
related_permissions:
  - medication_catalog.read
  - medication_catalog.write
related_paths:
  - backend/app/modules/medication_catalog/frontend/components/settings/MedicationCatalogSettingsPage.vue
last_verified_commit: 615ad10
---

# Catálogo de medicamentos

Se encuentra en **Ajustes → Clínico**. La lista está ordenada
alfabéticamente y paginada (20 por página).

## Qué puedes hacer

- **Buscar** por nombre (en vivo, con retardo).
- **Filtrar** por forma farmacéutica o mostrar solo los activos.
- **Añadir / editar**: nombre, dosis, unidad, forma, «requiere
  receta» y estado activo. Los nombres son únicos por clínica sin
  distinguir mayúsculas: un duplicado muestra un error en lugar de
  crear dos entradas.
- **Eliminar** con confirmación. Las recetas ya emitidas conservan su
  propia copia de los datos.
- **Cargar conjunto inicial**: añade la lista dental de 56
  medicamentos. Ejecutarlo dos veces no duplica nada.

Los medicamentos inactivos permanecen en la lista (estado gris) para
que el histórico y las recetas sigan teniendo sentido.

## Quién puede usarlo

Los administradores gestionan el catálogo; los dentistas tienen acceso
de lectura. Otros roles necesitan que se les conceda
`medication_catalog.read` / `.write` explícitamente desde la interfaz
de administración de módulos.
