---
module: razorpay
last_verified_commit: 8b8e9375
---

# razorpay — events

This module **does not register event handlers and emits no events of
its own**. It drives `payment_gateways`' services
(`PaymentRequestService.apply_webhook_event`/`confirm`/`fail`/
`expire`/`cancel`, `GatewayRefundService.complete`/`fail`) directly
from its webhook handler, which in turn call `payments.workflow`
directly — no event bus in this path (see
`docs/adr/0029-payment-gateway-adapter-architecture.md`).

## Published (indirectly, via `payment_gateways` → `payments`)

| Event | Triggered when |
|-------|----------------|
| `payment.recorded` / `payment.allocated` | webhook `payment.captured`/`order.paid`/`payment_link.paid`/`qr_code.credited` → `PaymentRequestService.confirm()` |
| `payment.refunded` | webhook `refund.processed` (or a synchronously-resolved refund) → `GatewayRefundService.complete()` |

## Subscribed

None. All state changes originate from this module's own webhook
endpoint (or a manual "refresh"/"cancel" call from the frontend),
never from the event bus.

See [`docs/events-catalog.md`](../../events-catalog.md) for the global
catalog and `docs/technical/payment_gateways/events.md` for the
service-layer side.
