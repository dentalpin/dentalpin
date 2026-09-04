---
module: supplier_items
last_verified_commit: 1642fd42
---

# supplier_items — permissions

Returned by `SupplierItemsModule.get_permissions()`
(relative names; the registry namespaces them as `supplier_items.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `supplier_items.read` | List and view supplier-item links | `GET /api/v1/supplier_items`, `GET /api/v1/supplier_items/{id}` |
| `supplier_items.write` | Create, update, or soft-delete a link | `POST /api/v1/supplier_items`, `PATCH /api/v1/supplier_items/{id}`, `DELETE /api/v1/supplier_items/{id}` |

## Role assignment

Role grants mirror `suppliers`/`contacts`: admin gets wildcard (`*`);
dentist and hygienist get `read` only; assistant and receptionist get
`read` + `write` (front-desk staff maintain the vendor pricing catalogue
day-to-day).

See `backend/app/modules/supplier_items/__init__.py` for the canonical role
table (`manifest.role_permissions`).

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/supplier_items/__init__.py`.
2. Grant it to roles in `manifest.role_permissions`.
3. Add a row to the table above.
4. Annotate the endpoint(s) with `Depends(require_permission(...))`.
5. Update `frontend/app/config/permissions.ts` if it gates UI.