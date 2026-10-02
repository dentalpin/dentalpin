---
module: billing
last_verified_commit: 2195ad0e
---

# Billing — permissions

Returned by `BillingModule.get_permissions()` (relative names
— the registry namespaces them as `billing.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `billing.read` | Listing and viewing invoices, invoice payments, history, PDF invoices, previewing PDFs, viewing billing settings, and fetching patient billing summaries. | `GET /invoices`, `GET /invoices/{invoice_id}`, `GET /invoices/{invoice_id}/payments`, `GET /invoices/{invoice_id}/history`, `GET /invoices/{invoice_id}/pdf`, `GET /invoices/{invoice_id}/pdf/preview`, `GET /settings`, `GET /patients/{patient_id}/summary`. |
| `billing.write` | Creating and modifying draft invoices, creating invoices from budgets, patching billing party details, deleting draft invoices, managing line items, issuing invoices, emailing invoices, issuing credit notes, and applying invoice payments. | `POST /invoices`, `POST /invoices/from-budget/{budget_id}`, `PUT /invoices/{invoice_id}`, `PATCH /invoices/{invoice_id}/billing-party`, `DELETE /invoices/{invoice_id}`, `POST /invoices/{invoice_id}/items`, `PUT /invoices/{invoice_id}/items/{item_id}`, `DELETE /invoices/{invoice_id}/items/{item_id}`, `POST /invoices/{invoice_id}/issue`, `POST /invoices/{invoice_id}/send-email`, `POST /invoices/{invoice_id}/credit-note`, `POST /invoices/{invoice_id}/payments`. |
| `billing.admin` | Managing invoice numbering series (list, create, update, reset), voiding issued invoices, and updating clinic billing settings. | `GET /series`, `POST /series`, `PUT /series/{series_id}`, `POST /series/{series_id}/reset`, `POST /invoices/{invoice_id}/void`, `PUT /settings`. |

## Role assignment

Declared in the module manifest
([`backend/app/modules/billing/__init__.py`](../../../backend/app/modules/billing/__init__.py)):

| Role          | Permissions    | Notes |
|---------------|----------------|-------|
| admin         | `*`            | Full control, including managing series, settings, and voiding invoices. |
| dentist       | `*`            | Full clinical and billing management. |
| hygienist     | `read`         | View invoices and patient billing summaries. |
| assistant     | `read`, `write`| Create draft invoices, apply payments, and issue invoices chairside. |
| receptionist  | `read`, `write`| Front-desk billing, creating and issuing invoices, payment collection. |

See `backend/app/core/auth/permissions.py` for the canonical role
table.

## Adding a new permission

1. Add the relative name to `get_permissions()` in
   `backend/app/modules/billing/__init__.py`.
2. Add it to the role mapping in `manifest.role_permissions` (same
   file) so the appropriate roles can use it on a fresh install.
3. Wire the gate on the endpoint via
   `Depends(require_permission("billing.<name>"))`.
4. Mirror in `frontend/app/config/permissions.ts` under
   `PERMISSIONS.billing.*` so the UI can call
   `usePermissions().can(PERMISSIONS.billing.<name>)`.
5. Add a row to this file with the matching endpoints.
6. Re-run `python backend/scripts/generate_catalogs.py`.
