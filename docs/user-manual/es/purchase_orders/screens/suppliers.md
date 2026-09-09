---
module: purchase_orders
screen: suppliers
route: /procurement/suppliers
last_verified_commit: 0f333000
related_endpoints:
  - GET /api/v1/suppliers
  - POST /api/v1/suppliers
  - PATCH /api/v1/suppliers/{id}
  - DELETE /api/v1/suppliers/{id}
related_permissions:
  - suppliers.read
  - suppliers.write
related_paths:
  - backend/app/modules/purchase_orders/frontend/pages/procurement/suppliers/index.vue
---

# Proveedores

En la entrada **Proveedores**. La lista muestra los proveedores de la
clínica por nombre, con búsqueda y filtros de preferidos e inactivos.

## Qué puedes hacer

- **Crear** un proveedor con datos de contacto, web, condiciones de
  pago, plazo en días y marca de preferido.
- **Editar** condiciones y contacto.
- **Eliminar** un proveedor. Los enlaces con artículos se conservan;
  si tiene enlaces activos se rechaza con un mensaje — deslístalos
  primero.
