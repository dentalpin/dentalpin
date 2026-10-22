---
module: billing
last_verified_commit: 9b2483eb491d80c7ceeef0aee2500d9458549047
---

# Billing — permissions

Returned by `BillingModule.get_permissions()` (relative names
— the registry namespaces them as `billing.<name>`).

| Permission | Allows | Required by |
|------------|--------|-------------|
| `billing.read` | Listing and viewing invoices, invoice payments, history, PDF invoices, previewing PDFs, viewing billing settings, and fetching patient billing summaries. | `GET /invoices`, `GET /invoices/{invoice_id}`, `GET /invoices/{invoice_id}/payments`, `GET /invoices/{invoice_id}/history`, `GET /invoices/{invoice_id}/pdf`, `GET /invoices/{invoice_id}/pdf/preview`, `GET /settings`, `GET /api/v1/settings/billing`, `GET /patients/{patient_id}/summary`. |
| `billing.write` | Creating and modifying draft invoices, creating invoices from budgets, patching billing party details, deleting draft invoices, managing line items, issuing invoices, emailing invoices, issuing credit notes, and applying invoice payments. | `POST /invoices`, `POST /invoices/from-budget/{budget_id}`, `PUT /invoices/{invoice_id}`, `PATCH /invoices/{invoice_id}/billing-party`, `DELETE /invoices/{invoice_id}`, `POST /invoices/{invoice_id}/items`, `PUT /invoices/{invoice_id}/items/{item_id}`, `DELETE /invoices/{invoice_id}/items/{item_id}`, `POST /invoices/{invoice_id}/issue`, `POST /invoices/{invoice_id}/send-email`, `POST /invoices/{invoice_id}/credit-note`, `POST /invoices/{invoice_id}/payments`. |
| `billing.admin` | Managing invoice numbering series (list, create, update, reset), voiding draft invoices, and updating clinic billing settings. | `GET /series`, `POST /series`, `PUT /series/{series_id}`, `POST /series/{series_id}/reset`, `POST /invoices/{invoice_id}/void`, `PUT /settings`, `PATCH /api/v1/settings/billing`. |

The generic settings routes live outside the module prefix, so their
paths are written in full. `PATCH /api/v1/settings/billing` requires
`billing.read` for every key it contains in addition to `billing.admin`;
a role with only the write permission is rejected.

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

### Why `dentist` holds `billing.admin`

`dentist` is granted `*`, which the permission matcher
([`backend/app/core/auth/permissions.py`](../../../backend/app/core/auth/permissions.py))
expands to `billing.read`, `billing.write` and `billing.admin` — the same
admin-tier reach `admin` has. This is intended and is deliberately not
narrowed ([maintainer confirmation on issue
#542](https://github.com/dentalpin/dentalpin/issues/542#issuecomment-6172678909)):

- The irreversible, AEAT-chained actions are **not** admin-tier. Issuing
  an invoice and issuing a credit note (how an already-issued invoice is
  reversed) are `billing.write`, held by `receptionist` and `assistant`
  too. Compliance chaining into Veri*Factu runs through a
  `BillingHookRegistry` hook — `VerifactuHook.on_invoice_issued`
  (`verifactu/hook.py`, registered in `on_activate` and resolved inline
  in the issuing path) — independently of who triggered the issue.
- `void` is draft-only (`InvoiceWorkflowService.can_void`,
  [`workflow.py`](../../../backend/app/modules/billing/workflow.py)), so
  it never touches an issued or fiscally-recorded invoice.
- The remaining admin actions a dentist can reach — numbering-series
  configuration and the clinic billing settings (default payment term,
  invoice footer, bank details) — are clinic fiscal configuration, not
  patient data. LOPD is unaffected: the grant exposes no personal data
  beyond what `billing.read` already returns.

Narrowing `dentist` to `read`/`write` was considered and rejected: it
would block a chairside void-and-recreate of a draft and the correction
of a misconfigured series, forcing a round trip to reception for routine
corrections, with no compliance benefit because the fiscally-sensitive
paths are already `billing.write`.

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
