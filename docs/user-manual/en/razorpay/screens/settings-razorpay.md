---
module: razorpay
screen: settings-razorpay
route: /settings/razorpay
related_endpoints:
  - GET /api/v1/razorpay/settings
  - PUT /api/v1/razorpay/settings
related_permissions:
  - razorpay.settings.read
  - razorpay.settings.write
related_paths:
  - backend/app/modules/razorpay/frontend/pages/settings/razorpay/index.vue
last_verified_commit: bd4b52b9
---

# /settings/razorpay

Connects the clinic's own Razorpay account so reception can collect
payments via UPI, QR, cards, and payment links directly from
DentalPin. Reached from **Settings → Billing & tax → Razorpay**, or
directly at `/settings/razorpay`.

## Permissions

Read-only for `razorpay.settings.read`. Every field and the **Save**
button additionally require `razorpay.settings.write` (admin by
default).

## Sections

1. **API credentials**
   - **Mode** — Test or Live. Use Test until a full collection has
     been verified end to end with a real Razorpay test-mode payment.
   - **Key ID** — from the Razorpay dashboard. Not secret; the browser
     needs it to open Razorpay's checkout.
   - **Key secret** — from the Razorpay dashboard. Write-only: once
     saved, the field always shows as empty with a hint that a secret
     is already configured. Leave it blank on a later save to keep the
     existing one; type a new value only to replace it.
   - **Active** — only an active, fully-configured connection is
     offered to reception as a collection method. Turn this off to
     hide the "Collect via Razorpay" action without losing the saved
     credentials.
2. **Webhook**
   - **Webhook URL** — a read-only, clinic-specific URL (includes this
     clinic's own id). Copy it into the Razorpay dashboard's webhook
     configuration for this account.
   - **Webhook secret** — the secret Razorpay signs webhook events
     with, found in the same dashboard screen where the webhook was
     created. Also write-only.
   - **Webhook health** — last received/processed timestamps and the
     last event type, so an admin can tell at a glance whether
     Razorpay is actually reaching this clinic. If Razorpay reports a
     problem, the last error and when it happened show here too.

## What Save does — and doesn't do

Saving stores the settings; it does **not** verify that the key/secret
pair actually works, or that the webhook is reachable — the only way
to confirm that is to try a real collection (Test mode) and check that
the webhook health block updates afterward. This screen has no
"Test connection" button in this release.

## Related screens

- `/payments` — where "Collect via Razorpay" appears once this screen
  shows **Active** with both a key secret and a webhook secret
  configured.
