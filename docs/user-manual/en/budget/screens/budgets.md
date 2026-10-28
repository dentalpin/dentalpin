---
module: budget
screen: list
route: /budgets
related_endpoints:
  - DELETE /api/v1/budget/budgets/{budget_id}
  - DELETE /api/v1/budget/budgets/{budget_id}/items/{item_id}
  - GET /api/v1/budget/budgets
  - GET /api/v1/budget/budgets/{budget_id}
  - GET /api/v1/budget/budgets/{budget_id}/history
  - GET /api/v1/budget/budgets/{budget_id}/pdf
  - GET /api/v1/budget/budgets/{budget_id}/pdf/preview
  - GET /api/v1/budget/budgets/{budget_id}/pdf/signed
  - GET /api/v1/budget/budgets/{budget_id}/signature
  - GET /api/v1/budget/budgets/{budget_id}/versions
  - POST /api/v1/budget/budgets
  - POST /api/v1/budget/budgets/{budget_id}/accept
  - POST /api/v1/budget/budgets/{budget_id}/accept-in-clinic
  - POST /api/v1/budget/budgets/{budget_id}/cancel
  - POST /api/v1/budget/budgets/{budget_id}/duplicate
  - POST /api/v1/budget/budgets/{budget_id}/items
  - POST /api/v1/budget/budgets/{budget_id}/reject
  - POST /api/v1/budget/budgets/{budget_id}/renegotiate
  - POST /api/v1/budget/budgets/{budget_id}/resend
  - POST /api/v1/budget/budgets/{budget_id}/send
  - POST /api/v1/budget/budgets/{budget_id}/send-reminder
  - POST /api/v1/budget/budgets/{budget_id}/set-public-code
  - POST /api/v1/budget/budgets/{budget_id}/unlock-public
  - PUT /api/v1/budget/budgets/{budget_id}
  - PUT /api/v1/budget/budgets/{budget_id}/items/{item_id}
related_permissions:
  - budget.read
  - budget.write
  - budget.admin
  - budget.renegotiate
  - budget.accept_in_clinic
related_paths:
  - backend/app/modules/budget/frontend/pages/budgets/index.vue
  - backend/app/modules/budget/router.py
last_verified_commit: a297ec1
---

# Budget list

The clinic's operational queue of budgets. Search by patient or
number, filter by workflow status, payment state, validity, and
assigned professional, sort, and open the detail to work each
budget.

## At a glance

- **Filters from two sources.** Status, professional, validity, and
  date range go to the native `GET /budgets` endpoint. The
  *Payment* filter (unpaid / partial / paid) is contributed by the
  payments module: the page calls
  `/payments/filters/budgets-by-status` and intersects the IDs.
- **Collected / Outstanding column** — filled by `payments` through
  the `budget.list.row.payments` slot. Uninstall payments and the
  column disappears without breaking anything.
- **Validity** — *Valid*, *Expiring soon* (next 7 days), *Expired*.
  Picking *Expiring soon* sets `valid_until_after=today` and
  `valid_until_before=today+7`.
- **Search** — the search box maps to `?search=` and matches budget
  number and patient. Filters live in the URL: a shared link is a
  shared filter.
- **Versioning.** Every renegotiation creates a new version without
  deleting the previous one. The list shows only the current version
  by default.

## Find a budget

1. Type the number or patient into the search bar.
2. Combine with the status or payment filters to narrow down.
3. Click a row to open the [detail](./budgets_id.md).

## Create a budget

> Requires `budget.write`.

1. Click **New budget**. It takes you to `/budgets/new`.
2. Select the patient and add catalog items, discounts, and VAT.
   See [New budget](./budgets_new.md).

## Row actions

> Some actions need extra permissions — see the permissions table.

- **Download PDF** — for the current budget state.
- **Duplicate** — creates a new draft with the same items.
- **Cancel / Delete** — admin only. Only a draft that no treatment plan
  uses can be deleted; cancel a sent or accepted quote instead, and
  reopen the plan to drop a plan's quote.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| Browse, search, and download PDFs | `budget.read` |
| Create, edit, send, duplicate | `budget.write` |
| Delete | `budget.admin` |
| Renegotiate (create a new version) | `budget.renegotiate` |
| Accept in-clinic (tablet signature) | `budget.accept_in_clinic` |

## Troubleshooting

- **No *Payment* filter shows up.** The `payments` module is not
  installed; the slot stays empty.
- **"Results truncated" warning.** The *Payment* filter intersects
  against a capped payments response — narrow by date or
  professional to reduce the universe.
- **A freshly renegotiated budget is missing.** The list shows the
  current version: the new version is visible, the previous one is
  available from the version history inside the detail.
