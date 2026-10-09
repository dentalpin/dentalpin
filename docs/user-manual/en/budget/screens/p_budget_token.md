---
module: budget
screen: public
route: /p/budget/[token]
related_endpoints:
  - GET /api/v1/budget/public/budgets/{token}
  - GET /api/v1/budget/public/budgets/{token}/meta
  - GET /api/v1/budget/public/budgets/{token}/pdf/signed
  - POST /api/v1/budget/public/budgets/{token}/accept
  - POST /api/v1/budget/public/budgets/{token}/reject
  - POST /api/v1/budget/public/budgets/{token}/verify
related_permissions:
related_paths:
  - backend/app/modules/budget/frontend/pages/p/budget/[token].vue
  - backend/app/modules/budget/router.py
last_verified_commit: a13bd29
---

# Public patient acceptance

The public view of a budget that the patient opens from the link
they receive by email or messaging. **No app session is required**;
the page authenticates via a token + a second-factor numeric code
per
[ADR 0006](../../../../adr/0006-budget-public-link-2-factor-auth.md).
From here the patient can review the budget, download the PDF, and
accept or reject it.

This screen is for the **patient**, not for clinic staff. We
document it here so the front desk knows what the patient sees when
the link is forwarded to them.

## At a glance

- **Prices are net.** Every treatment shows the discounted price (line + global discount); when there is a discount the original price appears struck through next to it, so the patient sees exactly what the footer total adds up from.
- **Two-factor.** The patient enters the numeric code the clinic
  provided (you configure it from the budget detail under *Set
  public code*). `POST /verify` is rate-limited and, on success,
  sets an HttpOnly session cookie scoped to
  `/api/v1/budget/public/budgets/{token}`. The cookie cannot unlock a
  different budget.
- **Idempotent first view.** The first time the patient opens the
  page (after verifying) we publish `budget.viewed` with a
  timestamp. Reopening does not emit more events.
- **Patient actions.** *Accept* and *Reject* are public actions:
  they create the signature record and publish
  `budget.accepted` / `budget.rejected`. Acceptance generates the
  signed PDF and stores its SHA-256 as a tamper-evident fingerprint.
- **Signed PDF.** After acceptance, *Download signed PDF* calls
  `GET /pdf/signed` with the cookie. Capped at 10 downloads per
  minute per token; each hit is logged in `BudgetAccessLog`.
- **Nothing personal before verification.** `GET /meta` answers with
  routing state and the clinic name only: no patient name, no budget
  number, total, or validity. Those arrive with the cookie-protected
  detail response after the code is accepted (#539).

## What the patient sees

1. A welcome screen with the clinic name and a code field.
2. After verifying: header with clinic + patient, line items with
   totals, validity, and assigned professional.
3. **Accept** and **Reject** buttons (Reject asks for a reason).
4. **Download PDF** of the budget.

## How to help a patient who is stuck

> Clinic-side actions.

- **Resend link** from the detail: *Resend*. Publishes
  `budget.reminder_sent`.
- **Change or generate a new public code** from *Set public code*.
- **Unlock after too many failed attempts** — endpoint
  `POST /unlock-public` (button on the detail when a lockout is
  active).

## Permissions

This is a public screen: no DentalPin permissions are tied to it.
The clinic-side actions that support it require `budget.write` in
the clinic (send, resend, set/change code, unlock).

## Troubleshooting

- **"Wrong code" repeatedly.** The patient is mistyping the code;
  after a few attempts the link is temporarily locked. Unlock it
  from the detail.
- **Patient accepts but no signed PDF.** The signed PDF is
  generated on accept; ask them to refresh after a few seconds. If
  it persists, check `BudgetAccessLog` for errors.
- **Session expired.** The cookie is per-token and short-lived. If
  the patient closes the browser they will have to re-enter the
  code.
