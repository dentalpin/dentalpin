---
module: billing
screen: create
route: /invoices/new
related_endpoints:
  - GET /api/v1/billing/series
  - GET /api/v1/billing/settings
  - POST /api/v1/billing/invoices
  - POST /api/v1/billing/invoices/{invoice_id}/items
related_permissions:
  - billing.read
  - billing.write
related_paths:
  - backend/app/modules/billing/frontend/pages/invoices/new.vue
  - backend/app/modules/billing/router.py
last_verified_commit: eab5bb31
---

# New invoice

Form to create a **free** invoice (without a budget). On save the
invoice is born as a draft (`draft`) and the
[detail](./invoices_id.md) opens so you can issue it when ready.

To invoice from an accepted budget use the
[budget-based screen](./invoices_from-budget_budgetId.md) — it
copies items with their price and VAT snapshots and avoids data
entry errors.

## At a glance

- **Receiver.** The patient. Billing data (name, tax ID, address,
  email) is not typed here: drafts read it live from the patient
  record and it is snapshotted when the invoice is issued. A badge
  tells you whether the patient's billing data is complete, with a
  link to fix it on the patient card.
- **Free lines.** Add catalog items with quantity, discount, VAT.
  You can also add manual lines (no catalog item) when needed for
  special charges.
- **No issuing yet.** Creating does not issue: it only saves the
  draft. Issuance lives on the detail.
- **Numbering.** Not assigned here; the fiscal number is set only
  when you **issue** (button on the detail), which takes the next
  one from the active series.
- **Payment terms.** Pre-filled with the clinic default from
  [Billing preferences](./settings_preferences.md)
  (`default_payment_term_days`); change it per invoice if needed.

## Create a free invoice

> Requires `billing.write`.

1. Pick the patient. If the badge says billing data is missing,
   complete it on the patient card first (link under the selector).
2. Add lines: catalog item, quantity, discount, VAT.
3. Review totals (subtotal, discount, VAT, total).
4. **Save**. The invoice is born in `draft`. To issue, open the
   [detail](./invoices_id.md) and click **Issue**.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| Access the form | `billing.read` |
| Create a draft | `billing.write` |

## Troubleshooting

- **"No active series" warning.** No series is marked active for
  the fiscal year under *Settings → Invoice series*. You can save
  the draft but not issue it.
- **Cannot find a catalog item.** Make sure it is active and that
  your role has `catalog.read`. If you need a special charge, add
  a manual line.
- **No *Different payer* button.** Available on any draft (no
  extra permission). If it doesn't show, refresh; it may be a
  load failure of the catalog or the clinic settings.
