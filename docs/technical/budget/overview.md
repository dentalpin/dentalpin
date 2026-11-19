---
module: budget
last_verified_commit: 0000000
---

# Budget — technical overview

> _Scaffolded stub — replace with proper documentation when this module is next touched._

Auto-discovered facts about the `budget` module. See the module's
own notes at `backend/app/modules/budget/CLAUDE.md` for context
the scaffold could not infer.

## Frontend acceptance

The budget detail page owns its inline accept/reject form; the public
budget page uses the shared signature canvas.

## API surface

- `DELETE /api/v1/budget/budgets/{budget_id}`
- `DELETE /api/v1/budget/budgets/{budget_id}/items/{item_id}`
- `GET /api/v1/budget/budgets`
- `GET /api/v1/budget/budgets/{budget_id}`
- `GET /api/v1/budget/budgets/{budget_id}/history`
- `GET /api/v1/budget/budgets/{budget_id}/pdf`
- `GET /api/v1/budget/budgets/{budget_id}/pdf/preview`
- `GET /api/v1/budget/budgets/{budget_id}/pdf/signed`
- `GET /api/v1/budget/budgets/{budget_id}/signature`
- `GET /api/v1/budget/budgets/{budget_id}/versions`
- `POST /api/v1/budget/budgets`
- `POST /api/v1/budget/budgets/{budget_id}/accept`
- `POST /api/v1/budget/budgets/{budget_id}/accept-in-clinic`
- `POST /api/v1/budget/budgets/{budget_id}/cancel`
- `POST /api/v1/budget/budgets/{budget_id}/duplicate`
- `POST /api/v1/budget/budgets/{budget_id}/items`
- `POST /api/v1/budget/budgets/{budget_id}/reject`
- `POST /api/v1/budget/budgets/{budget_id}/renegotiate`
- `POST /api/v1/budget/budgets/{budget_id}/resend`
- `POST /api/v1/budget/budgets/{budget_id}/send`
- `POST /api/v1/budget/budgets/{budget_id}/send-reminder`
- `POST /api/v1/budget/budgets/{budget_id}/set-public-code`
- `POST /api/v1/budget/budgets/{budget_id}/unlock-public`
- `PUT /api/v1/budget/budgets/{budget_id}`
- `PUT /api/v1/budget/budgets/{budget_id}/items/{item_id}`

## Frontend

- `backend/app/modules/budget/frontend/pages/budgets/index.vue` → `/budgets`
- `backend/app/modules/budget/frontend/pages/budgets/[id].vue` → `/budgets/[id]`
- `backend/app/modules/budget/frontend/pages/budgets/new.vue` → `/budgets/new`
- `backend/app/modules/budget/frontend/pages/p/budget/[token].vue` → `/p/budget/[token]`

## Permissions

`read`, `write`, `admin`, `renegotiate`, `accept_in_clinic`

See [`./permissions.md`](./permissions.md) for the full role mapping.

## Events

- **Emits:** _(none)_
- **Subscribes:** `odontogram.treatment.performed`, `treatment_plan.budget_sync_requested`, `treatment_plan.treatment_added`, `treatment_plan.treatment_removed`

See [`./events.md`](./events.md) for the per-event detail (when the
module participates in the event bus).

## See also

- Module CLAUDE notes: `backend/app/modules/budget/CLAUDE.md`
- [Documentation portal contract](../../technical/documentation-portal.md)
