---
module: inventory_reorder
last_verified_commit: 0f333000
---

# inventory_reorder — Permissions

Gating permissions returned by `get_permissions()` (registry prefixes
with `inventory_reorder`):

| Permission | Effect | Roles |
|---|---|---|
| `inventory_reorder.read` | View reorder suggestions | `admin` (`*`), `dentist`, `hygienist`, `assistant`, `receptionist` |
| `inventory_reorder.write` | Generate draft purchase orders from suggestions | `admin` (`*`), `assistant`, `receptionist` |

Reference: `backend/app/core/auth/permissions.py` (runtime source),
`frontend/app/config/permissions.ts` (frontend mirror).

## Endpoint → permission

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/v1/inventory_reorder/suggestions` | `inventory_reorder.read` |
| `POST` | `/api/v1/inventory_reorder/orders` | `inventory_reorder.write` |

## Notes

- Clinicians (`dentist`, `hygienist`) see suggestions, but only
  front-desk staff and admins can act on them — mirroring the
  `purchase_orders` role grant (front desk runs procurement).
- Same strings back the Copilot agent tools
  (`list_reorder_suggestions` → `read`, `generate_reorder_orders` →
  `write`).