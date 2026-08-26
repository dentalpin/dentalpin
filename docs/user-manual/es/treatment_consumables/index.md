---
module: treatment_consumables
last_verified_commit: 47983b05
---

# Consumibles por tratamiento

Vincula cada tratamiento del catálogo con los artículos de inventario
que consume, y en qué cantidad (p. ej. endodoncia → 2 viales de
anestésico). Mapeo puro: el stock **no** se descuenta automáticamente.

Requiere tener instalado el módulo `inventory`.

## Pantallas

- [Consumibles por tratamiento](./screens/index.md): histórico de
  vínculos con buscadores hacia ambos módulos, edición de cantidad y
  desvinculación con confirmación.
