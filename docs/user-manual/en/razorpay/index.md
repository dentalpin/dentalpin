---
module: razorpay
last_verified_commit: 8fb8f8cb
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

- `/payments` — click **New payment** as usual. For India clinics with
  an active Razorpay configuration, the method row inside that same
  modal offers three extra chips alongside cash/card/bank
  transfer/etc.: **UPI QR**, **Razorpay** (card checkout), and
  **Payment link**. There is no separate Razorpay button next to "New
  payment" — picking one of the three chips swaps the modal into the
  collection panel (QR code / Checkout.js / copyable link), which polls
  until Razorpay confirms the payment and only then closes the modal.
  Gateway-collected payments show a small "Razorpay · UPI"-style badge
  under the row's date/method line that opens the transaction detail
  (audit trail, allocation, and refund history).
- Patient detail → Pagos tab — the same three chips appear inside that
  tab's own "Cobrar" modal, next to the manual methods.

## Technical references

- [Technical overview](../../../technical/razorpay/overview.md)
- [Permissions](../../../technical/razorpay/permissions.md)
- [Events](../../../technical/razorpay/events.md)
- [payment_gateways overview](../../../technical/payment_gateways/overview.md) — the provider-neutral module this one plugs into
- [ADR 0029 — payment gateway adapter architecture](../../../adr/0029-payment-gateway-adapter-architecture.md)
