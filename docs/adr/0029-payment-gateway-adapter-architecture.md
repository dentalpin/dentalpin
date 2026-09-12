# 0029 — Payment gateway adapter architecture (payment_gateways + razorpay)

- **Status:** accepted
- **Date:** 2026-09-03
- **Deciders:** DentalPin Core Team
- **Tags:** modules, payments, india, finance, security

## Context

India clinics need to collect patient payments electronically — UPI,
QR codes, cards, payment links — through a real gateway (Razorpay
first; PhonePe and Stripe are on the roadmap). Two constraints shape
the design:

1. **`payments` is the financial ledger** (ADR 0010): a `Payment` is
   immutable and means money has *actually* been received. A gateway
   collection attempt is asynchronous — started, waiting on the
   customer, authorized, captured, failed, expired, or cancelled — and
   none of those intermediate states may leak into the ledger as a
   `Payment`.
2. **Provider credentials and vendor wire logic must never live in
   core.** This is the same shape problem ADR 0016 solved for
   notification channels (email vs. WhatsApp vs. future SMS): one
   contract, a registry, and a provider module per vendor.

## Decision

Two modules, mirroring the `notifications` / `whatsapp_kapso` split:

- **`payment_gateways`** owns the provider-neutral contract
  (`adapters/base.py`: `GatewayAdapter` Protocol + typed request/result
  dataclasses), the registry (`adapters/registry.py`,
  `gateway_registry`), and the `PaymentRequest` /
  `GatewayRefundRequest` lifecycle (`service.py`). It depends on
  `patients`, `budget`, `payments` and is the *only* module allowed to
  call `payments.workflow.record_payment` / `refund_payment` from a
  gateway confirmation.
- **`razorpay`** is a provider module. It depends only on
  `payment_gateways`, implements `GatewayAdapter` as `RazorpayAdapter`,
  and registers it into `gateway_registry` from `on_activate()` — never
  at import time (ADR 0020: an uninstalled provider is never
  registered). All Razorpay SDK/API calls, webhook signature
  verification, credentials (Fernet-encrypted, mirroring
  `whatsapp_kapso`), and provider-specific ids live here exclusively.
  A future `phonepe` or `stripe` module implements the same contract
  and never touches `payment_gateways` or `payments`.

### Module boundary — what never crosses it

- `payment_gateways` must not depend on `billing`.
- Neither module adds a provider name, credentials, provider
  transaction id, or a status column to core `payments.Payment` /
  `payments.Refund`. The *only* place that knows a given `Payment` was
  gateway-collected at all is `payment_gateways.PaymentRequest`
  (`payment_id` FK, set once, at confirmation) — `payments` itself
  stays provider-agnostic, exactly as ADR 0010 requires of the ledger.
- Invoice allocation is never gateway logic. A `PaymentRequest` carries
  the same `allocation_input` (`budget` / `on_account`) and `context`
  (e.g. `{"prefer_invoice_id": ...}`) that
  `payments.workflow.record_payment` already accepts from any other
  caller (e.g. billing's own invoice-payment endpoint) — the existing
  billing event bridge (`payment.allocated` → `payment_bridge`) does
  the invoice-side work unchanged.

### The `PaymentRequest` state machine

`payment_gateways.constants.PaymentRequestState`:

```
pending -> awaiting_customer_action -> authorised_awaiting_capture -> succeeded
   \-> failed / expired / cancelled (from pending or awaiting_customer_action)
```

`succeeded` / `failed` / `expired` / `cancelled` are terminal.
`validate_payment_request_transition` rejects any move not in the
table — including re-entering a terminal state — so an adapter bug
can never resurrect a `succeeded` request or silently overwrite a
`failed` one. Confirming an *already-terminal* request (a late webhook
racing a timeout sweep) is a documented no-op, not an error: it is
recorded on the row (`raw_status_snapshot`) for manual reconciliation,
but never creates a `Payment` — a stale confirmation must not silently
resurrect an attempt the clinic has already moved on from.

`GatewayRefundRequest` mirrors this with its own small machine
(`requested -> processing -> completed | failed`), gating the creation
of a core `payments.Refund` behind `completed`.

### Confirmation is atomic and idempotent — never from a browser redirect

`PaymentRequestService.confirm()` is the single code path that creates
a `Payment` from a gateway confirmation. It:

1. No-ops if the request is already `succeeded` (or any other terminal
   state) — the primary defense against **duplicate webhook
   delivery**.
2. Rejects a confirmation whose amount disagrees with
   `requested_amount` — protects the allocation-sum invariant
   `payments.workflow.record_payment` itself enforces.
3. Calls `record_payment(...)` and sets
   `payment_id` / `state=succeeded` **in the same DB transaction** —
   both writes commit together or not at all (FastAPI's `get_db()`
   commits once at the end of the request; nothing in this path
   commits early except the deliberate failure-persistence case
   below).
4. Is only ever called after the caller (a provider's webhook handler)
   has independently verified the provider's signature and holds a row
   lock on the `PaymentRequest`
   (`get_locked_by_provider_reference`, `SELECT ... FOR UPDATE`) — so
   two concurrent deliveries of the same event serialize instead of
   racing on the idempotency check.

A hard, unique DB index on `(provider_key, provider_payment_reference)`
is the backstop: even a bug that bypassed the row lock and the
in-service check cannot produce two `PaymentRequest` rows claiming the
same provider payment.

A browser-side "payment succeeded" callback (Razorpay Checkout.js's
`handler`) is **never** treated as authoritative — the collection UI
only reacts to it by polling harder; the only thing that ever flips a
request to `succeeded` is a verified webhook (or, for a manual
refresh, an equivalent server-side status pull through the same
`confirm()` path).

### Why a failed attempt still gets committed before the error is raised

`create_and_initiate()` / `request_refund()` mark the row `failed` and
call `db.commit()` *before* raising `GatewayError` back to the router.
This looks unusual, but it is deliberate: FastAPI's `get_db()`
dependency rolls back the whole request session on any exception —
without the explicit early commit, a provider-side rejection (bad
credentials, network outage) would leave no `PaymentRequest` row at
all, and the collection UI would have nothing to show a `failed` state
for. The explicit commit trades a small amount of transactional purity
for an honest audit trail on the one path where "nothing happened" is
not actually true — a provider order/refund attempt was made.

### Why `Refund` is created only from `complete()`, never inline

Some providers (Razorpay included) resolve a refund synchronously in
the initiate API response. Even then, `GatewayRefundService.request_refund`
routes the synchronous case through the same `complete()` method the
asynchronous webhook path uses, rather than constructing a
`payments.Refund` inline — there is exactly one code path that ever
writes that row, so its idempotency and cap-enforcement logic cannot
drift between the two cases.

## Consequences

### Good

- The provider boundary is enforced mechanically: `test_module_isolation.py`
  fails the build the moment `razorpay` imports anything outside
  `payment_gateways`, or `payment_gateways` imports anything outside
  `patients`/`budget`/`payments`.
- Adding PhonePe or Stripe is a new module + one `register()` call —
  zero changes to `payment_gateways` or `payments`.
- `payments.Payment`/`Refund` stay exactly as provider-agnostic as ADR
  0010 already required them to be; nothing about this feature widens
  that ledger's surface area beyond two new values in
  `PAYMENT_METHODS` (`upi`, `netbanking`).
- Round-trip uninstall is clean: `razorpay` uninstall unregisters its
  adapter; `payment_gateways` uninstall is blocked while any request or
  refund is still in flight (non-terminal state), so removing the
  module can never orphan a checkout or refund a clinic is actively
  waiting on.

### Bad / accepted trade-offs

- The refundable-amount pre-check (`GatewayRefundService._refundable_amount`)
  only counts *completed* refunds — two refund requests issued in fast
  concurrent succession could both pass the pre-check before either
  completes. `payments.workflow.refund_payment`'s own row-locked cap
  check at `complete()` time is the final backstop (the second one
  fails there, converting to a `failed` `GatewayRefundRequest` instead
  of an over-refund) — accepted for v1 rather than adding cross-request
  locking for an edge case admin UIs rarely trigger.
- Per-clinic Razorpay webhook URLs carry the `clinic_id` in the path
  (`/api/v1/razorpay/webhook/{clinic_id}`) rather than resolving
  tenancy from an account-level header, since a direct (non-Partner)
  Razorpay integration has no such header. The `clinic_id` is only
  ever used to select *which secret to verify against* — a wrong or
  guessed id can never forge events without also knowing that clinic's
  actual webhook secret.

## Alternatives considered

- **Event bus for gateway confirmation** (mirroring most other
  cross-module writes). Rejected: the confirmation path needs the
  *same* atomicity billing's own direct-call path to
  `payments.workflow` already relies on (see ADR 0010's "orchestrator"
  consequence) — a webhook has exactly one authoritative consumer,
  unlike notifications' genuinely fan-out channel sends.
- **Store provider/status fields directly on `payments.Payment`.**
  Rejected outright by the task's own boundary and by ADR 0010: the
  core ledger must stay meaning "money received," full stop, and
  provider-neutral.
- **Razorpay module calls `payments.workflow` directly.** Rejected —
  would require `razorpay.depends` to include `patients`/`budget`/
  `payments`, defeating the point of the adapter boundary and making a
  future PhonePe module duplicate the same wiring instead of only
  implementing `GatewayAdapter`.

## How to verify the rule still holds

- `backend/tests/test_module_isolation.py` — fails if `razorpay`
  imports anything outside `payment_gateways`, or `payment_gateways`
  imports anything outside its declared `depends`.
- `backend/tests/modules/payment_gateways/` — registry, state-machine
  transitions (including illegal/no-op cases), atomic confirm,
  duplicate-webhook idempotency, refund cap enforcement, permission
  checks — all against a `FakeAdapter`, no network.
- `backend/tests/modules/razorpay/` — webhook signature verification,
  payload parsing, settings secret-masking/isolation, and an
  end-to-end "verified webhook creates exactly one `Payment` with
  `method=upi`" test.

## References

- Issue #263 (PR 1 of #365)
- `backend/app/modules/payment_gateways/` (contract + registry +
  service)
- `backend/app/modules/razorpay/` (adapter + client + webhook)
- ADR 0001 (modular plugin architecture)
- ADR 0010 (payments as a primitive module)
- ADR 0016 (channel-adapter architecture — the pattern this mirrors)
- ADR 0019 (transactional event handlers)
- ADR 0020 (install-state gates runtime — `on_activate()` registration)
