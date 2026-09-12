# payment_gateways — CHANGELOG

## Unreleased

- Initial implementation (#263, PR 1 of #365): provider-neutral gateway
  adapter contract (`GatewayAdapter` Protocol + typed request/result
  dataclasses) and process-wide registry, mirroring
  `notifications`/ADR 0016. `PaymentRequest` (pre-payment async
  lifecycle) and `GatewayRefundRequest` (async refund lifecycle) with
  explicit, validated state machines — every transition (including
  no-ops on already-terminal states) goes through
  `constants.validate_payment_request_transition`/
  `validate_refund_transition`.
- `PaymentRequestService.confirm()` atomically creates the core
  `payments.Payment` (via `payments.workflow.record_payment`) and
  marks the request `succeeded`, in one DB transaction. Idempotent:
  duplicate webhook delivery is a no-op, backed by a unique index on
  `(provider_key, provider_payment_reference)` as a defense-in-depth
  backstop against the service-layer check being bypassed.
- `GatewayRefundService` mirrors this for refunds — a core
  `payments.Refund` is created only from `complete()`, never inline,
  even when a provider resolves a refund synchronously.
- Endpoints under `/api/v1/payment_gateways/` reuse `payments.record.*`
  permissions rather than declaring new ones (see router.py).
- Migrations: `pg_0001` (own Alembic branch, chained off `pay_0004`).
- Tests: registry (register/unregister/idempotent re-register,
  razorpay's `on_activate()`), `PaymentRequest` create/confirm/
  fail/expire/cancel (incl. idempotency, amount-mismatch rejection,
  adapter-failure persistence, illegal-transition rejection),
  `GatewayRefundRequest` request/complete (incl. duplicate-completion
  idempotency, synchronous-provider fast path, cap enforcement,
  permission gating) — all against a `FakeAdapter`, no network.
