# razorpay module

The first production payment gateway provider — UPI intent/checkout,
dynamic QR, cards, and payment links, for India clinics. Community-style
provider module: registers a `RazorpayAdapter` into `payment_gateways`'s
registry from `on_activate()`. The thin "wire": adapter + signed
webhook + settings. All lifecycle/ledger logic lives in
`payment_gateways`/`payments`.

Issue #263 (PR 1 of #365). ADR 0016 (channel adapters — the pattern
this module's registration mirrors), ADR 0029 (payment gateway adapter
architecture).

## Public API

Routes at `/api/v1/razorpay/`:

| Method | Path | Auth |
|---|---|---|
| GET/PUT | `/settings` | `razorpay.settings.read` / `.write` |
| POST | `/webhook/{clinic_id}` | **PUBLIC** — per-clinic HMAC signature |

Gateway collection/refund/status endpoints live in `payment_gateways`
(`/api/v1/payment_gateways/...`) — this module never duplicates them.

## Dependencies

`manifest.depends = ["payment_gateways"]`. The ONLY cross-module
import is `app.modules.payment_gateways.adapters`/`.constants`/
`.models` (all in `depends`). `payment_gateways` does NOT depend on
this module — the adapter registers into the runtime registry.
Deliberately does **not** depend on `patients`/`budget`/`payments`
directly: patient contact info for checkout prefill is resolved by
`payment_gateways.service` (which has `patients` in *its* depends) and
handed to the adapter as `GatewayCustomerInfo` — this module only ever
talks to the neutral contract.

## Permissions

`razorpay.settings.read`, `razorpay.settings.write` (admin only).

## Channel adapter

`RazorpayAdapter` (`adapter.py`) implements
`payment_gateways.adapters.GatewayAdapter`; `RazorpayModule.on_activate()`
registers it into `gateway_registry` — idempotent, never at import
time (ADR 0020). `supports()` = an active `RazorpaySettings` row with
both `key_id` and a decryptable `key_secret` exists for the clinic.

- `initiate_payment` — `upi`/`card` → Razorpay Orders API
  (`payment_capture=1`, auto-capture) + a Checkout.js options payload;
  `qr` → the QR Codes API (`type=upi_qr`, `fixed_amount`); `payment_link`
  → the Payment Links API. The requested method is only a *hint* for
  which API to call — the confirmed `payments.Payment.method` always
  comes from what Razorpay reports as actually used
  (`constants.map_provider_method`), since a "UPI intent" checkout can
  be completed with a saved card.
- `verify_payment_status` — best-effort manual-refresh pull (order
  payments / QR code payments / payment-link status). Never the
  primary confirmation path; any ambiguity resolves to "no change,"
  never a guess.
- `initiate_refund`/`refresh_refund_status` — Razorpay's refund API,
  mapped onto `GatewayRefundInitResult`/`GatewayRefundStatusResult`.

## Webhook (trust boundary)

`POST /webhook/{clinic_id}` is public (auth is per-route; no global
gate). It:

1. resolves the clinic's `RazorpaySettings` by the `clinic_id` path
   segment — used **only** to select which secret to verify against,
   never trusted for tenancy on its own,
2. verifies `X-Razorpay-Signature` = HMAC-SHA256(raw_body,
   clinic's webhook_secret), constant-time compare — a wrong/guessed
   `clinic_id` can never forge events without also knowing that
   clinic's actual secret,
3. parses the payload via `RazorpayAdapter.parse_webhook_event` into a
   neutral `GatewayWebhookEvent`,
4. dispatches `payment_*` events onto a row-locked
   `PaymentRequest` (`payment_gateways.service.PaymentRequestService`)
   and `refund_*` events onto a row-locked `GatewayRefundRequest`
   (`GatewayRefundService`) — both looked up and locked before any
   state change, so concurrent duplicate deliveries serialize.

Unknown/unconfigured clinics and unrecognized event types are
accept-and-ignore (`200`), never an error — Razorpay would otherwise
retry a webhook URL forever. A `GatewayError` (data problem — amount
mismatch, illegal transition) is logged to `RazorpaySettings` webhook
health and still answers `200` (retrying won't fix a data problem); a
genuine transport/programmer error answers `500` so Razorpay retries.

## Razorpay method → core payment method mapping

`constants.RAZORPAY_METHOD_MAP`: `upi→upi`, `card→card`,
`netbanking→netbanking`, `emi→card`, `wallet→other`, `paylater→other`,
anything unrecognized → `other` (never raises — a future Razorpay
method addition must not break confirmation).

## Events

Emits none. Confirms/fails/expires/cancels `PaymentRequest`s and
completes/fails `GatewayRefundRequest`s through `payment_gateways`'
services directly (see that module's CLAUDE.md for why no event bus).

## Secrets

`key_secret` and `webhook_secret` are Fernet-encrypted at rest via
`app.core.email.encryption` (project-wide util), exactly like
`whatsapp_kapso`. `key_id` is stored **plaintext** — Razorpay's own key
id is meant to be handed to the browser (Checkout.js needs it in the
`key` option) and is not a secret on its own. Neither secret is ever
returned by `GET`/`PUT /settings` — only `has_key_secret`/
`has_webhook_secret` booleans.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch `razorpay` (`rzp_0001`), anchored on the bare core
  revision (`razorpay_settings` only FKs to `clinics`).

## Gotchas

- **The requested checkout rail (`upi`/`qr`/`card`/`payment_link`) is
  not the confirmed payment method.** Always read `confirmed_method`
  off the webhook's `GatewayConfirmation`, mapped through
  `map_provider_method` — never assume the rail the customer started
  with.
- **`payment_capture=1` is always set at order creation** (see
  `client.create_order`) — there is no manual authorize-then-capture
  step in v1. A `payment.authorized` webhook where
  `payload.payment.entity.captured` is already `true` is redundant
  (`payment.captured` follows immediately) and is accept-and-ignored,
  not turned into an `authorised_awaiting_capture` transition.
- **Refund events carry a different lookup key than payment events.**
  `GatewayWebhookEvent.provider_reference` (order/QR/link id) locates a
  `PaymentRequest`; `refund_provider_reference` (Razorpay refund id)
  locates a `GatewayRefundRequest`. Never conflate them — see
  `router.py::_dispatch_payment_event`/`_dispatch_refund_event`.
- **`GatewayRefundRequest.provider_payment_reference` is a
  denormalized copy** of `PaymentRequest.provider_payment_reference`,
  set once at refund-request creation — deliberately, so
  `initiate_refund` never has to lazy-load the `payment_request`
  relationship in an async context (that would raise
  `MissingGreenlet`).
- **Amounts are integers in paise, never float.** `client.to_paise`/
  `from_paise` always route through `Decimal`, mirroring
  `payments.service._quantize`'s own float-contamination guard.

## Frontend

- **Composable**: `useRazorpay` (settings + payment_gateways client).
- **Components**: `RazorpaySettingsCardsSlot` (settings hub card),
  `RazorpayMethodChips` (`payments.create.methods` slot — three chips,
  UPI QR / Razorpay checkout / payment link, inside the core
  `PaymentCreateModal`'s method row, India-clinic-gated, disabled with
  a hint until settings are active), `RazorpayCollectPanel` (the
  hand-off panel the core modal renders on submit: opens the
  `PaymentRequest`, shows QR / Checkout.js / link, polls, `created`
  only once `succeeded`, `back` on cancel/try again),
  `RazorpayPaymentBadge` (`payments.list.row.meta` slot — renders
  nothing for a non-gateway payment; only calls `gateway-info` when
  `reference` starts with `razorpay:`), `RazorpayTransactionDetailModal`
  (audit trail, allocation, settlement, refund history + "refund via
  Razorpay" action). The core modal is never forked: manual methods,
  date, reference/notes and the allocation editor stay its own.
- **Pages**: `/settings/razorpay`. Permission-gated with
  `usePermissions().can()`.
- **i18n**: all nine host locales (`frontend/i18n/locales/`): de, en, es,
  fr, hu, it, pl, pt, ta.
- **Checkout.js**: loaded dynamically (`<script src="https://checkout.razorpay.com/v1/checkout.js">`)
  only when the Razorpay rail is chosen — never eagerly on page load.
- **Never treats the browser `handler` callback as confirmation** — it
  only triggers a poll; the modal shows `succeeded` only once
  `PaymentRequest.state` says so.
- **PhonePe is not rendered.** It has no adapter in this PR — the rail
  is scoped for a follow-up, not stubbed as a disabled chip.

## Tests

- **Backend**: `tests/modules/razorpay/` — amount conversion, method
  mapping, webhook signature verification, webhook payload parsing
  (all event types incl. unrecognized/accept-ignore), settings
  isolation/masking/permission, end-to-end webhook → exactly one
  `Payment` (incl. duplicate-delivery idempotency, failed-path, refund
  completion).

## Related ADRs

- `docs/adr/0016-channel-adapter-architecture.md`
- `docs/adr/0020-install-state-gates-runtime.md`
- `docs/adr/0029-payment-gateway-adapter-architecture.md`

## CHANGELOG

See `./CHANGELOG.md`.
