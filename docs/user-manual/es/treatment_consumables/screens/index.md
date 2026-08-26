---
module: treatment_consumables
screen: index
route: /treatment-consumables
related_endpoints:
  - GET /api/v1/treatment_consumables
  - POST /api/v1/treatment_consumables
  - PATCH /api/v1/treatment_consumables/{id}
  - DELETE /api/v1/treatment_consumables/{id}
  - GET /api/v1/treatment_consumables/link-options
related_permissions:
  - treatment_consumables.read
  - treatment_consumables.write
related_paths:
  - backend/app/modules/treatment_consumables/frontend/pages/treatment-consumables/index.vue
last_verified_commit: 38a49ffe
---

# Consumibles por tratamiento

Asocia cada tratamiento del catálogo con los artículos de inventario
que utiliza, y cuántos (p. ej. endodoncia → 2 viales de anestésico).
Mapeo puro: el stock **no** se descuenta automáticamente.

## Qué puedes hacer

- **Vincular un consumible**: cada lado tiene su propio buscador —
  busca un tratamiento, busca un artículo de inventario, indica la
  cantidad y una nota opcional («por sesión», «solo si hay cirugía») y
  confirma. Ambos lados se validan contra tu clínica; vincular dos
  veces el mismo par se rechaza con un aviso.
- **Editar** la cantidad y la nota de cualquier vínculo existente.
- **Desvincular** con confirmación.
- La tabla histórica muestra todos los vínculos con los nombres
  resueltos de ambos módulos, la cantidad con la unidad del artículo y
  la nota. Del más reciente al más antiguo, paginados.

## Quién puede usarlo

Los administradores gestionan los vínculos; los dentistas tienen
acceso de lectura. Requiere el módulo `inventory` instalado.
