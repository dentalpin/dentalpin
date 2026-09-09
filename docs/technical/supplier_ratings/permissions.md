---
module: supplier_ratings
last_verified_commit: 0f333000
---

# supplier_ratings — Permissions

Gating permissions returned by `get_permissions()` (registry prefixes
with `supplier_ratings`):

| Permission | Effect | Roles |
|---|---|---|
| `supplier_ratings.read` | View supplier scorecards and reviews | `admin` (`*`), `dentist`, `hygienist`, `assistant`, `receptionist` |
| `supplier_ratings.write` | Create/edit/delete manual ratings | `admin` (`*`), `assistant`, `receptionist` |

Reference: `backend/app/core/auth/permissions.py` (runtime source),
`frontend/app/config/permissions.ts` (frontend mirror).

## Endpoint → permission

| Method | Path | Permission |
|---|---|---|
| `GET` | `/api/v1/supplier_ratings` | `supplier_ratings.read` |
| `GET` | `/api/v1/supplier_ratings/{supplier_id}` | `supplier_ratings.read` |
| `GET` | `/api/v1/supplier_ratings/reviews/{review_id}` | `supplier_ratings.read` |
| `POST` | `/api/v1/supplier_ratings/reviews` | `supplier_ratings.write` |
| `PATCH` | `/api/v1/supplier_ratings/reviews/{review_id}` | `supplier_ratings.write` |
| `DELETE` | `/api/v1/supplier_ratings/reviews/{review_id}` | `supplier_ratings.write` |

## Notes

- Clinicians (`dentist`, `hygienist`) can read scorecards but not rate
  suppliers — mirroring `purchase_orders` (front desk runs procurement).
- Same strings back the Copilot agent tools
  (`list_supplier_ratings`/`get_supplier_rating` → `read`,
  `create_supplier_review` → `write`).