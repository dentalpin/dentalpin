---
module: billing
screen: from-budget
route: /invoices/from-budget/[budgetId]
related_endpoints:
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - GET /api/v1/budget/budgets/{budget_id}
  - POST /api/v1/billing/invoices/from-budget/{budget_id}
related_permissions:
  - billing.read
  - billing.write
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/from-budget/[budgetId].vue
  - backend/app/modules/billing/router.py
last_verified_commit: 6c91240
---

# Invoice from budget

Wizard to issue an invoice from an accepted budget on the `budget`
module. Supports **full or partial billing**: by default all
uninvoiced items, but you can pick which lines and quantities to
include.

## At a glance

- **Only from accepted budgets.** If the budget is not in
  `accepted` (or already has a non-cancelled active invoice), the
  *Create invoice* button on the budget detail does not appear.
- **Per-item check.** Each budget line shows `invoiced / total`.
  You can only add the remainder or part of it; the backend
  rejects exceeding the pending quantity.
- **Price snapshot.** Lines are copied from the budget with their
  current price and VAT — so the invoice isn't affected by later
  catalog changes.
- **Discounts travel with the lines.** The quote's line discount
  **and** its global discount (spread across the lines, ex-tax) are
  written on each invoice line — the invoice totals what the patient
  signed. On partial invoicing the discount is prorated by the
  invoiced quantity. The preview shows the same figures the invoice
  will have.
- **Receiver.** Defaults to the patient. You can switch to a
  different payer (company, insurer, family member) before issuing.

## Invoice from a budget

> Requires `billing.write`.

1. You arrive here from the budget detail (*Create invoice*).
2. Review the list: tick / untick lines and adjust the quantities
   to invoice.
3. If the invoice goes to a third party, configure the alternate
   payer.
4. **Create invoice**. The endpoint
   `POST /billing/invoices/from-budget/{budget_id}` is called with
   the selected items. The invoice is born in `draft` with the
   snapshots copied.
5. To issue, open the [detail](./invoices_id.md) and click
   **Issue**.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| Load the wizard and see the budget | `billing.read` |
| Create the invoice | `billing.write` |

## Troubleshooting

- **No *Create invoice* button on the budget.** The budget is not
  `accepted`, already has a non-cancelled invoice, or every item
  is invoiced 100%.
- **Backend returns 400 on create.** You picked more quantity than
  pending. Check `invoiced_quantity` vs `quantity` per line.
- **A budget line is missing.** It is already 100% invoiced
  (`invoiced_quantity == quantity`). To revert, void the previous
  invoice and re-enter this wizard.
