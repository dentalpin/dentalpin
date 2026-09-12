# payment_gateways module

Provider-neutral payment gateway **contract, registry, and
`PaymentRequest`/`GatewayRefundRequest` lifecycle**. Mirrors
`notifications`' channel-adapter architecture (ADR 0016): this module
owns the contract and the registry, never a provider implementation.
`razorpay` is the first (and so far only) provider module; `phonepe`
and `stripe` are expected to follow the exact same shape.

Issue #263 (PR 1 of #365). See ADR 0029 (payment gateway adapter
architecture) for the full rationale — module boundary, state machine,
atomic/idempotent confirmation, and why failed attempts are still
committed before the error is raised.

## Public API

Routes mounted at `/api/v1/payment_gateways/`. Every endpoint reuses
`payments.record.{read,write,refund}` — see `router.py`'s module
docstring for why (same cross-module permission-reuse precedent as
india_gst reusing `billing.write`).

| Path | Method | Permission |
|---|---|---|
| `/requests` | POST | `payments.record.write` |
| `/requests/{id}` | GET | `payments.record.read` |
| `/requests/{id}/refresh` | POST | `payments.record.write` |
| `/requests/{id}/cancel` | POST | `payments.record.write` |
| `/payments/{payment_id}/gateway-info` | GET | `payments.record.read` |
| `/refunds` | POST | `payments.record.refund` |
| `/refunds/{id}` | GET | `payments.record.read` |
| `/payments/{payment_id}/refunds` | GET | `payments.record.read` |

## Dependencies

`manifest.depends = ["patients", "budget", "payments"]`. **Never add
billing** — mirrors payments' own ADR 0010 boundary; this module calls
`payments.workflow.record_payment`/`refund_payment` directly (legal,
declared in `depends`) and never imports billing.

## Permissions

None of this module's own (`get_permissions()` → `[]`) — see the
Public API table above. `role_permissions: {"admin": ["*"]}` is
declared anyway so the manifest-consistency test's "every module has
at least admin" invariant holds if a module-own permission is ever
added later.

## Tools exposed

None (`get_tools()` → `[]`). Not agent-exposed in v1 — gateway
collection is a UI-driven flow (patient present, choosing a rail,
waiting on a webhook), not something an agent should initiate
unattended.

## Events emitted

None. Gateway confirmation calls `payments.workflow.record_payment`/
`refund_payment` **directly**, in the same transaction, rather than
through the event bus — see ADR 0029 "Alternatives considered" for why
(a webhook has exactly one authoritative consumer, unlike
notifications' genuinely fan-out channel sends). `payments` itself
still publishes its usual `payment.recorded`/`payment.allocated`/
`payment.refunded` events from inside `record_payment`/`refund_payment`
— this module doesn't change that.

## Events consumed

None.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- `on_activate()` is a no-op — this module never registers anything
  itself; a *provider* module (`razorpay`) registers its adapter here
  from its own `on_activate()`.
- `uninstall()` blocks if any `PaymentRequest` or `GatewayRefundRequest`
  is still in a non-terminal state (`pending`/`awaiting_customer_action`/
  `authorised_awaiting_capture` for requests; `requested`/`processing`
  for refunds) — removing the module must never orphan a checkout or
  refund a clinic is actively waiting on. Terminal rows never block
  uninstall; they're just history.
- Own Alembic branch `payment_gateways` (`pg_0001`), anchored on core
  `0001` with `depends_on=("pay_0005",)` since `payment_requests`/
  `gateway_refund_requests` FK into `payments`/`refunds`.

## Gotchas / non-obvious invariants

- **`payments.Payment` carries no provider field, ever.** The *only*
  place that knows a given `Payment` was gateway-collected at all is
  this module's own `PaymentRequest.payment_id` (set once, at
  confirmation). `GET /payments/{id}/gateway-info` is the read path
  everything else (transaction detail UI, refund lookup) goes through
  — never assume a `Payment` carries gateway metadata itself.
- **Confirmation is the only path that creates a `Payment` from a
  gateway flow — and it's idempotent by construction.**
  `PaymentRequestService.confirm()` no-ops on an already-terminal
  request (not just `succeeded`) rather than raising, because a late
  "succeeded" webhook racing our own timeout sweep is a real scenario,
  not a bug — see ADR 0029. Callers (webhook handlers) MUST hold a row
  lock (`get_locked_by_provider_reference`, `SELECT ... FOR UPDATE`)
  before calling `confirm()`/`apply_webhook_event()` — the lock is what
  makes concurrent duplicate deliveries serialize instead of racing on
  the "already succeeded?" check.
- **A `GatewayRefundRequest` never creates a core `Refund` except from
  `complete()`** — even the fast path where a provider resolves a
  refund synchronously in its initiate response still routes through
  `complete()` rather than constructing a `Refund` inline. One code
  path, one place the idempotency/cap logic can drift.
- **The refundable-amount pre-check only counts *completed* core
  refunds**, not other `GatewayRefundRequest`s still `requested`/
  `processing`. Two refund attempts issued in fast succession could
  both pass this pre-check — `payments.workflow.refund_payment`'s own
  row-locked cap check at `complete()` time is the real backstop (the
  loser gets converted to `failed`, never a silent over-refund). See
  ADR 0029's accepted trade-offs.
- **A `GatewayError` raised from `create_and_initiate`/`request_refund`'s
  provider-failure branch is preceded by an explicit `db.commit()`.**
  FastAPI's `get_db()` rolls back the whole request session on any
  exception; without the early commit, a `failed` row created just
  before raising would vanish along with the reserved idempotency key,
  leaving nothing for the collection UI to show a "failed" state for.
  See ADR 0029's "Why a failed attempt still gets committed" section
  before removing what looks like a redundant commit.
- **`allocation_input` and `context` are stored as JSONB — always pass
  Decimal/UUID values through `model.model_dump(mode="json")` before
  handing them to the service**, never a raw `.model_dump()`. asyncpg's
  JSONB encoder cannot serialize a `Decimal` directly (see
  `router.py::create_request`).
- **A browser-side checkout "success" callback is never authoritative.**
  The collection UI (owned by the provider module) only uses it as a
  cue to poll harder; only a verified webhook (or an equivalent
  server-pulled status through `confirm()`) ever flips a request to
  `succeeded`.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0010-payments-as-primitive-module.md`
- `docs/adr/0016-channel-adapter-architecture.md`
- `docs/adr/0020-install-state-gates-runtime.md`
- `docs/adr/0029-payment-gateway-adapter-architecture.md`

## CHANGELOG

See `./CHANGELOG.md`.
