---
module: treatment_consumables
last_verified_commit: 47983b05
---

# Consumibles por tratamiento

Vincula cada tratamiento del catálogo con los artículos de inventario
que consume, y en qué cantidad (p. ej. endodoncia → 2 viales de
anestésico). Al registrar la realización de un tratamiento vinculado, las cantidades asociadas pueden descontarse automáticamente del stock. Las notas del vínculo son informativas y no establecen condiciones para el descuento.

Requiere tener instalado el módulo `inventory`.

## Pantallas

- [Consumibles por tratamiento](./screens/index.md): histórico de
  vínculos con buscadores hacia ambos módulos, edición de cantidad y
  desvinculación con confirmación.
