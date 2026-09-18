# Changelog — integrations module

## Unreleased

### `patients:write` token scope

- `SUPPORTED_TOKEN_SCOPES` now also admits `patients:write`
  (`triggers.py`). First consumer is the MCP module
  (`mcp` `create_patient`); the public REST API stays read-only.
  This line supersedes the original "patients:read only" note below.

### Shared token authentication

- `IntegrationsService.authenticate_token(db, plaintext)` — the single
  shared entry point for every `dp_` token consumer. Resolves a plaintext
  to its active (unrevoked) `ApiToken` row, or `None` (unknown prefix /
  unknown hash / revoked); on success it enforces the per-token
  fixed-window rate limit (60/min + 1000/day, in-process; raises the new
  `RateLimitError` when over) and stamps `last_used_at`. The caller owns
  the commit.
- `public.py`'s `get_api_token_context` now delegates to the helper
  (removing its inline hash lookup) and maps `RateLimitError` to 429 with
  `X-RateLimit-*` headers from the shared limiter.
- The `mcp` module authenticates through the same helper, so MCP traffic
  is rate-limited per token and shows up in `last_used_at` too (see the
  `mcp` CHANGELOG).

### CI hygiene (ruff 0.16.5 drift)

- Reformatted the two multi-line `client.get(...)` calls in
  `tests/modules/integrations/test_public_api.py` that the newest (unpinned)
  ruff `format --check` flags — keeps `backend-lint` green for any PR built on
  the current tree.

### Phase 2 follow-up (ported from PR #348)

- `GET /public/ping` — token introspection (clinic, name, scopes); the
  auth test a Zapier/Make app calls. Valid token required, no scope.
- Authenticated public requests now stamp `ApiToken.last_used_at`
  (the column existed since `int_0002` but was never written).
- `GET /public/patients` grows format-tolerant exact-match params
  `phone` / `email` / `national_id` (whitespace/dash/case ignored) —
  the find leg of the search-or-create pattern (issue #65 §5).
  The generic `search` filter is unchanged.

### Phase 2 (issue #65)

- **Six new webhook triggers** (appointment.scheduled, appointment.cancelled,
  appointment.no_show, budget.sent, budget.accepted, budget.rejected) — all
  transactional (published with `db=`; ADR 0019 guard test covers them).
  Deferred (emit without `db=`, blocked): patient.updated, invoice.issued,
  invoice.paid, payment.recorded.
- **Stable `event_id`** on every `WebhookDelivery` (migration `int_0003`):
  all deliveries queued for the same source event publish share one UUID,
  so a receiver can dedupe across subscriptions (issue #65 §1).
- **Token-authenticated public data-read API** (`/api/v1/integrations/public/`):
  `GET /public/patients` (list/search by name/phone/email/national_id) and
  `GET /public/patients/{id}` — authenticated via `Authorization: Bearer dp_...`,
  scope-enforced (`patients:read`), rate-limited per token (60/min, 1000/day,
  surfaced in `X-RateLimit-*` headers), clinic-scoped off the token's own
  `clinic_id`. Reuses `PatientService.list_patients` (no logic duplicated).
- **Frozen sample payloads** — one `sample_payloads/<event>.json` per
  supported trigger, loaded by `sample_payload_loader.py`; tests assert
  100 % coverage and `clinic_id` parseability (issue #65 §3).
- `PublicPatientResponse` schema — PII-aware curated subset (id, names,
  contact, national_id, date_of_birth, status; no billing fields or notes).
- `schemas.py` error message updated to drop "Phase 1" wording now that
  Phase 2 events are supported.
- `triggers.py` expanded: `SUPPORTED_EVENT_TYPES` grows from 2 to 8 events;
  `SUPPORTED_TOKEN_SCOPES` unchanged (`patients:read`).
- `test_uninstall_roundtrip.py` downgrade target updated to `integrations@-3`.
- `test_unsupported_event_type_rejected` now uses `invoice.issued` (a real
  but unsupported/deferred bus event) instead of `budget.sent`, which became
  a supported trigger in Phase 2.

### Phase 1 (issue #65)

- Initial module: webhook subscription CRUD, outbox-backed delivery with
  retry/backoff/auto-disable, Stripe-style HMAC-SHA256 signing, and one
  working trigger (`patient.created`).
- Added second Phase 1 trigger `appointment.completed`, sharing an
  `_enqueue` helper with `on_patient_created` (identical apart from
  the `EventType`).
- Added `ApiToken` model + admin CRUD (`GET/POST /tokens`, `POST
  /tokens/{id}/revoke`). Plaintext is `dp_` + `secrets.token_urlsafe(32)`
  (recognizable prefix for secret-scanning tools), shown once,
  SHA-256-hashed at rest (not Fernet/bcrypt — see `models.ApiToken`
  docstring). `scopes` validated against a closed catalog
  (`SUPPORTED_TOKEN_SCOPES`), not free text. No consumer endpoint
  yet — the public data-read API is a follow-up PR.
- Added `occurred_at` to every enqueued webhook payload.
- SSRF guard on `target_url` (`url_safety.py`) — not in the original
  issue scoping. Validated at subscription create/update (async, via
  the event loop's own resolver — not a Pydantic validator, which
  can't `await`) and again immediately before every dispatch (a
  hostname can be repointed after creation; this narrows the window
  rather than fully defending against DNS rebinding, since httpx
  re-resolves on connect). Rejects non-`https` schemes and any
  hostname/literal that resolves to a private, loopback, link-local,
  reserved, or multicast address, including the cloud metadata IP.
  `client.py` also sets `follow_redirects=False` so a validated
  request can't be redirected to an unvalidated internal URL.
- Signing header renamed `X-Integrations-Signature` →
  `X-DentalPin-Signature` (a public contract, so committing to the
  product name rather than the internal module name).
- Fixed `update_subscription`: `description` can now actually be
  cleared to `null` (was previously unclearable).
- `get_tools()` added, returning `[]` (new-module checklist).
- `manifest.depends` stays `["patients"]` — `agenda` (the
  `appointment.completed` publisher) is not a dependency, since
  consuming an event doesn't require depending on its publisher.
- Added `CLAUDE.md` and this file.
- Added the round-trip uninstall test required for `removable=True`
  modules (`test_uninstall_roundtrip.py`, `alembic_roundtrip` marker).
