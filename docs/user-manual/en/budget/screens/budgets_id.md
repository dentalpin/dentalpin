---
module: budget
screen: detail
route: /budgets/[id]
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
  - backend/app/modules/budget/frontend/pages/budgets/[id].vue
  - backend/app/modules/budget/router.py
last_verified_commit: 4c419ba
---

# Budget detail

Full view of one budget: header with patient info, a main column
with the line items and totals, and a sidebar with actions, metadata,
and the payments card contributed by the payments module. This is
where the budget moves through `draft → sent → accepted` and gets
signed, invoiced, or renegotiated.

## At a glance

- **Two-column layout.** Left: budget line items with catalog item,
  tooth, surfaces, quantity, discount, and VAT. Right (top to
  bottom): **payments** card (slot `budget.detail.sidebar`, filled
  by `payments`), **totals** (subtotal, discount, VAT, total),
  **info** (number, version, validity, creator, linked plan).
- **Status chip** in the header. Available actions depend on it.
- **Versioning.** Each renegotiation creates a new version linked
  via `parent_budget_id`; history is shown under *Version history*.
- **Signature and PDFs.** An accepted budget stores a
  `BudgetSignature` plus a signed PDF whose SHA-256 is kept as a
  tamper-evident hash. Two downloads exist: unsigned PDF and
  signed PDF.
- **Create invoice.** When the budget is *accepted* and still has
  uninvoiced items, a *Create invoice* button appears and takes you
  to `/invoices/from-budget/{id}`.

## Edit lines

> Requires `budget.write` and `draft` status.

1. Click **Edit** on a line or **Add item** below the table.
2. Change catalog item, tooth, surfaces, quantity, discount, or
   VAT. Totals recompute on save.
3. The backend rewrites the totals invariant on save (no `update`
   event yet).

## Send to the patient

> Requires `budget.write`.

1. Click **Send to patient**. The budget transitions to `sent`, a
   public code is generated, and the email goes out.
2. `budget.sent` is published so messaging modules can complement
   the email.
3. The sidebar then shows the [public link](./p_budget_token.md)
   card with the verification code.

## Accept or reject

> Requires `budget.write` for online acceptance,
> `budget.accept_in_clinic` for in-clinic signed acceptance.

1. **Accept (online)** — used when the patient accepts via the
   public link. Creates a `BudgetSignature` and a signed PDF.
   Publishes `budget.accepted`.
2. **Accept in clinic** — button only visible with the matching
   permission. Opens the tablet signature modal (drawn signature).
   Same result as the online acceptance.
3. **Reject** — records a reason and publishes `budget.rejected`.

## Renegotiate

> Requires `budget.renegotiate`.

1. Click **Renegotiate**. Creates a new version linked to the
   current one; the previous becomes historical.
2. Edit items and save. Publishes `budget.renegotiated`.

## Permissions

| What you see / can do | Permission |
|-----------------------|------------|
| View detail, lines, version history, download PDF | `budget.read` |
| Edit lines, send, accept online, reject, cancel, duplicate | `budget.write` |
| Accept by signing in-clinic | `budget.accept_in_clinic` |
| Renegotiate (create a new version) | `budget.renegotiate` |
| Delete | `budget.admin` |

## Troubleshooting

- **No *Create invoice* button.** The budget is not accepted yet
  (valid: `accepted`), or it already has a non-cancelled invoice,
  or every item is already invoiced
  (`invoiced_quantity == quantity`).
- **Cannot edit lines.** The budget is no longer in `draft`. To
  change prices or quantities on a sent/accepted budget you must
  **renegotiate** (requires `budget.renegotiate`).
- **No payments card.** The `payments` module is not installed.
  The sidebar shows only totals and info.
- **Signed PDF returns 404.** The budget is not accepted yet — the
  signed PDF only exists from the `accepted` state on.
- **An action failed.** The error toast shows the reason the server
  gave, not a generic message. The common ones are *Cannot send
  empty budget* (add at least one line first), *Patient has no email
  address* (fill it in on the patient record, or untick *Send email*
  and mark it as delivered by hand), and *Cannot send budget from
  status 'sent'* (it was already sent — reload the page).
