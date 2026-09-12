---
module: razorpay
last_verified_commit: 8b8e9375
---

# Razorpay

Landing page for the `razorpay` module in the end-user manual. This
module lets an India clinic collect patient payments electronically
through Razorpay — UPI, a scannable QR code, cards, and payment
links — directly from the `/payments` list and the patient's payment
tab. A payment only ever shows as received once Razorpay itself
confirms it; nothing here changes how a manually-recorded (cash, card
terminal, bank transfer) payment works.

## Screens

- `/settings/razorpay` — configure the clinic's Razorpay connection.
  See [screens/settings-razorpay.md](./screens/settings-razorpay.md).

The collection panel and transaction detail live inline on `/payments`
(and the patient Pagos tab) rather than on their own route — see the
payments module's own user manual for that screen, and
[Related screens](#related-screens) below for what this module adds
to it.

## Permissions

- `razorpay.settings.read` / `.write` — connect/manage the gateway
  (admin only by default).
- Collecting a payment or issuing a refund through Razorpay uses the
  same `payments.record.write` / `payments.record.refund` permissions
  as manually recording a payment — no separate grant needed.

## Related screens

- `/payments` — a "Collect via Razorpay" button appears next to "New
  payment" for India clinics with an active Razorpay configuration.
  Gateway-collected payments show a small "Razorpay · UPI"-style badge
  that opens the transaction detail (audit trail, allocation, and
  refund history).
- Patient detail → Pagos tab — the same "Collect via Razorpay" action
  appears below the manual "Cobrar" button.

## Technical references

- [Technical overview](../../../technical/razorpay/overview.md)
- [Permissions](../../../technical/razorpay/permissions.md)
- [Events](../../../technical/razorpay/events.md)
- [payment_gateways overview](../../../technical/payment_gateways/overview.md) — the provider-neutral module this one plugs into
- [ADR 0029 — payment gateway adapter architecture](../../../adr/0029-payment-gateway-adapter-architecture.md)
