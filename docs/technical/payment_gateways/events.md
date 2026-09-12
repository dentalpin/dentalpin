---
module: payment_gateways
last_verified_commit: 8b8e9375
---

# payment_gateways — events

This module **does not register event handlers and publishes no
events of its own**. A gateway confirmation calls
`payments.workflow.record_payment`/`refund_payment` **directly** (in
the same DB transaction), rather than going through the event bus —
see ADR 0029 "Alternatives considered" for why (a webhook has exactly
one authoritative consumer, unlike a genuinely fan-out send).

## Published (indirectly, via `payments`)

`record_payment`/`refund_payment` still publish their usual events
from inside those calls — this module doesn't change or duplicate
that:

| Event | Triggered when |
|-------|----------------|
| `payment.recorded` | `PaymentRequestService.confirm()` calls `record_payment` |
| `payment.allocated` | same call, once per allocation row |
| `payment.refunded` | `GatewayRefundService.complete()` calls `refund_payment` |

See `docs/technical/payments/events.md` (via `payments/CLAUDE.md`) for
those payloads and subscribers (notably billing's `payment_bridge`,
which still does the invoice-side allocation work unchanged for a
gateway-collected payment).

## Subscribed

None.

See [`docs/events-catalog.md`](../../events-catalog.md) for the global
catalog.
