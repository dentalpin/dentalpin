---
module: integrations
last_verified_commit: ab94969a
---

# integrations — overview

Webhook subscriptions (REST Hooks) + token-authenticated public data-read
API for third-party automations — issue #65. Phase 1 wired the outbox,
HMAC signing, and two triggers. Phase 2 expands to eight triggers, adds a
stable per-event `event_id`, a public read API under `/public/`, and frozen
sample payloads for every trigger. Zapier/Make/n8n apps and the admin UI
are follow-up scope.

## What it is

### Admin surface (JWT + RBAC)

`/api/v1/integrations/webhooks/subscriptions` — CRUD for webhook
subscriptions. `/api/v1/integrations/tokens` — issue/revoke API tokens.
Staff (`integrations.subscriptions.*` / `integrations.tokens.*`).

- `GET /api/v1/integrations/webhooks/subscriptions`
- `POST /api/v1/integrations/webhooks/subscriptions`
- `PATCH /api/v1/integrations/webhooks/subscriptions/{subscription_id}`
- `DELETE /api/v1/integrations/webhooks/subscriptions/{subscription_id}`
- `GET /api/v1/integrations/tokens`
- `POST /api/v1/integrations/tokens`
- `POST /api/v1/integrations/tokens/{token_id}/revoke`

### Public data-read API (API-token + scope)

Authenticated with `Authorization: Bearer dp_...` against the token's
`scopes`. Rate-limited per token (60 req/min, 1000 req/day), surfaced in
`X-RateLimit-*` headers. Clinic-scoped off the token's own `clinic_id`
(no JWT, no `get_clinic_context`).

- `GET /api/v1/integrations/public/patients` — list/search by name / phone /
  email / national_id (paginated). Requires scope: `patients:read`.
- `GET /api/v1/integrations/public/patients/{patient_id}` — get one.
  Requires scope: `patients:read`.

Tokens may also carry `patients:write`, which is consumed by the MCP
module (`create_patient` — see `docs/technical/mcp/overview.md`) rather
than any endpoint under `/public/`.

Response: `PublicPatientResponse` — curated PII subset (id, names, contact,
national_id, date_of_birth, status; no billing fields, no notes).

## Supported webhook triggers (8)

| Event | Publisher | db= |
|-------|-----------|-----|
| `patient.created` | patients/service.py | ✓ |
| `appointment.completed` | agenda/service.py | ✓ |
| `appointment.scheduled` | agenda/service.py | ✓ |
| `appointment.cancelled` | agenda/service.py | ✓ |
| `appointment.no_show` | agenda/service.py | ✓ |
| `budget.sent` | budget/workflow.py | ✓ |
| `budget.accepted` | budget/workflow.py | ✓ |
| `budget.rejected` | budget/workflow.py | ✓ |

Deferred (publish without `db=`): patient.updated, invoice.issued,
invoice.paid, payment.recorded. Adding them requires fixing the publisher
to pass a session.

## Data model

`webhook_subscriptions` — clinic-owned config row (target URL, event types,
encrypted signing secret, auto-disable state). `webhook_deliveries` — both
the outbox queue row and the audit record for one delivery attempt; carries
`event_id` (stable UUID shared across all subscriptions hit by the same
publish). `api_tokens` — clinic-owned bearer token (name, scopes,
SHA-256 `token_hash`, `revoked_at`/`revoked_reason`).

Migrations: `int_0001` (initial schema), `int_0002` (api_tokens),
`int_0003` (event_id column + index on webhook_deliveries).

## Delivery

`gateway.py`'s `WebhookGateway` mirrors `NotificationGateway`'s
outbox shape 1:1: DB-only enqueue, a scheduled 45s dispatch tick with
`FOR UPDATE SKIP LOCKED` batching, same exponential backoff. A
subscription auto-disables after 10 consecutive failures. Every dispatched
envelope carries `event`, `event_id`, `delivery_id`, and `data`.

## Signing

Stripe's exact scheme (`signing.py`): header
`X-DentalPin-Signature`, `t=<unix_ts>,v1=<hex_hmac>`, HMAC-SHA256
over `timestamp.body`, 5-minute tolerance.

## SSRF guard

`url_safety.py` — `target_url` is clinic-supplied and the server POSTs to
it directly, so it's checked (async, via the event loop's own resolver)
at subscription create/update and again immediately before every dispatch.
Requires `https`, rejects any hostname or IP literal that resolves to a
private, loopback, link-local, reserved, or multicast address.

## Sample payloads

`sample_payloads/<event>.json` — frozen per trigger; loaded by
`sample_payload_loader.py`. Tests assert 100 % coverage.

## Tenancy

Every query filters by `clinic_id`; a cross-clinic subscription id
404s rather than 403s, matching the rest of the repo's convention.
Public API queries use the token's own `clinic_id` (no JWT context).

## Constraints

Own Alembic branch (`integrations`), rooted on core `"0001"` — no FK
into another module's tables.

See [`./permissions.md`](./permissions.md) and
[`./events.md`](./events.md) for the full detail, and
`backend/app/modules/integrations/CLAUDE.md` for the design rationale.
