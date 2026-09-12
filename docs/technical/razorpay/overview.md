---
module: razorpay
last_verified_commit: 8b8e9375
---

# razorpay — overview

The first production payment gateway provider — UPI intent/checkout,
dynamic QR, cards, and payment links, for India clinics. Community-style
module, installable/removable. Issue #263, PR 1 of #365.

## What it is

The thin vendor "wire" under the gateway-adapter architecture (ADR
0022, mirroring ADR 0016):

- **`RazorpayAdapter`** (`adapter.py`) implements
  `payment_gateways.adapters.GatewayAdapter` and registers into
  `payment_gateways.adapters.gateway_registry` from `on_activate()`
  (never at import time). Delivers `upi`/`qr`/`card`/`payment_link`.
- **`client.py`** — thin `httpx` REST client (no SDK dependency),
  HTTP Basic Auth `key_id:key_secret`, mirroring `whatsapp_kapso`'s/
  verifactu's own client pattern.
- **Public `/webhook/{clinic_id}`** — Razorpay's signed webhook,
  verified by a per-clinic HMAC secret; the clinic is resolved by the
  URL path segment (only ever used to pick which secret to verify
  against, never trusted for tenancy on its own).
- **Settings**: per-clinic mode (test/live), credentials
  (Fernet-encrypted), webhook secret, active flag, webhook health
  (last received/processed, last event type, last error).

All lifecycle/ledger logic (`PaymentRequest`/`GatewayRefundRequest`
state machine, calling into `payments.workflow`) lives in
`payment_gateways`. This module owns no ledger state — only its own
`razorpay_settings` table.

## Data model

- `razorpay_settings` — one row per clinic: `mode`, `key_id`
  (plaintext — meant for the browser), `key_secret_encrypted`,
  `webhook_secret_encrypted`, `is_active`, `is_verified`, webhook
  health fields.

## Module boundary

`manifest.depends = ["payment_gateways"]` — nothing else. Patient
contact info for checkout prefill is resolved by
`payment_gateways.service` (which has `patients` in its own depends)
and handed to this module's adapter as `GatewayCustomerInfo`; this
module never imports `patients`/`budget`/`payments` directly. Enforced
by `tests/test_module_isolation.py`.

## Method mapping

`constants.RAZORPAY_METHOD_MAP` translates Razorpay's own
`payment.entity.method` values onto core `payments.PAYMENT_METHODS`:
`upi→upi`, `card→card`, `netbanking→netbanking`, `emi→card`,
`wallet→other`, `paylater→other`, anything unrecognized → `other`. The
*requested* rail (which checkout flow was started) is only a hint;
the *confirmed* method always comes from what Razorpay reports.
