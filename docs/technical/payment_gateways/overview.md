---
module: payment_gateways
last_verified_commit: 8b8e9375
---

# payment_gateways — overview

Provider-neutral payment gateway contract, registry, and the
`PaymentRequest`/`GatewayRefundRequest` async lifecycle. Mirrors the
channel-adapter architecture (ADR 0016) that `notifications` uses for
email/WhatsApp. Official, installable/removable. Issue #263, PR 1 of
#365. Full rationale: ADR 0029.

## What it is

- **`adapters/`** — the public contract (`GatewayAdapter` Protocol,
  typed request/result dataclasses: `GatewayCheckoutResult`,
  `GatewayConfirmation`, `GatewayWebhookEvent`,
  `GatewayRefundInitResult`, etc.) and the idempotent `gateway_registry`.
  A provider module (`razorpay`) `depends=["payment_gateways"]` and
  calls `gateway_registry.register(...)` from its own `on_activate()`.
- **`service.py`** — `PaymentRequestService` (create/initiate → confirm
  → succeeded, or fail/expire/cancel) and `GatewayRefundService`
  (request → complete/fail). The *only* code allowed to call
  `payments.workflow.record_payment`/`refund_payment` from a gateway
  flow.
- **`router.py`** — `POST /requests`, `GET/POST .../refresh|cancel`,
  `GET /payments/{id}/gateway-info`, `POST /refunds`, `GET /refunds/{id}`,
  `GET /payments/{id}/refunds`. Reuses `payments.record.*` permissions
  (no permissions of its own).
- **`constants.py`** — the `PaymentRequestState`/`GatewayRefundState`
  StrEnums and their validated transition tables.

No frontend layer — this module is backend-only infrastructure. UI
(collection panel, transaction detail, refunds) is owned entirely by
the provider module. The collection rails are chips the provider
registers into the core "New payment"/"Cobrar" modal's method row via
the `payments.create.methods` slot; on submit the modal hands its
validated form to the provider's own panel (QR / checkout / link, wait,
expiry), so the core modal is never forked. The payment-list badge uses
the additive `payments.list.row.meta` slot, since it only needs to
render alongside existing content.

## Data model

- `payment_requests` — one row per collection attempt: `provider_key`,
  `requested_amount`/`currency`/`requested_method`, `state`,
  `allocation_input`/`context` (JSONB, verbatim inputs to
  `record_payment`), `provider_reference`/`provider_payment_reference`
  (unique per provider once assigned), `checkout_payload_snapshot`
  (non-secret — what the frontend was handed), `payment_id` (FK,
  set once at confirmation).
- `gateway_refund_requests` — one row per refund attempt: `payment_id`
  (the core `Payment`), `payment_request_id`, `provider_payment_reference`
  (denormalized from the request), `state`, `provider_refund_reference`,
  `refund_id` (FK, set once at completion).

Neither table duplicates anything on `payments.Payment`/`Refund` — no
provider name, status, or fees live in the core ledger. See
`docs/adr/0029-payment-gateway-adapter-architecture.md`.

## Module boundary

`manifest.depends = ["patients", "budget", "payments"]`. **Never add
billing.** The only cross-module imports are into those three
(patient contact lookup, allocation validation, and the direct
`record_payment`/`refund_payment` calls) — enforced by
`tests/test_module_isolation.py`.
