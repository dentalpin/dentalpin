---
module: medication_catalog
last_verified_commit: 76b1273a
---

# Catálogo de medicamentos

Lista de medicamentos de la clínica bajo **Ajustes → Clínico**:
nombre, dosis, unidad, forma farmacéutica y estado
recetado/activo. Incluye un conjunto inicial dental idempotente de 56
medicamentos; los administradores lo gestionan y los dentistas lo
consultan. Es la fuente de datos para las recetas (generación de
documentos).

## Pantallas

- [Catálogo de medicamentos](./screens/clinical-medications.md):
  búsqueda, filtros por forma/estado, alta/edición/borrado con
  protección contra duplicados y cargador del conjunto inicial.
