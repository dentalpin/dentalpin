---
module: integrations
last_verified_commit: d426572
---

# integrations — overview

Webhook subscriptions (REST Hooks) for third-party automations —
issue #65 Phase 1. The public data-read API that will authenticate
with the API tokens issued here, the full trigger catalog, and
Zapier/Make/n8n integrations are follow-up scope, not in this module
yet.

## What it is

Admin-authenticated CRUD under `/api/v1/integrations/webhooks/
subscriptions` and `/api/v1/integrations/tokens`. A clinic subscribes
to one or more event types with a target URL; the module signs and
delivers a JSON payload to that URL whenever a subscribed event
fires. Phase 1 wires two triggers, `patient.created` and
`appointment.completed`. A clinic can also issue bearer API tokens
(name + scopes), shown once on creation, revocable — no endpoint
consumes them yet.

- `GET /api/v1/integrations/webhooks/subscriptions`
- `POST /api/v1/integrations/webhooks/subscriptions`
- `PATCH /api/v1/integrations/webhooks/subscriptions/{subscription_id}`
- `DELETE /api/v1/integrations/webhooks/subscriptions/{subscription_id}`
- `GET /api/v1/integrations/tokens`
- `POST /api/v1/integrations/tokens`
- `POST /api/v1/integrations/tokens/{token_id}/revoke`

## Data model

`webhook_subscriptions` — clinic-owned config row (target URL, event
types, encrypted signing secret, auto-disable state).
`webhook_deliveries` — both the outbox queue row and the audit record
for one delivery attempt, same split as
`notifications.models.CommunicationMessage`.
`api_tokens` — clinic-owned bearer token (name, scopes, SHA-256
`token_hash`, `revoked_at`/`revoked_reason`). Never Fernet-encrypted
like the webhook secret — the plaintext is never read back, only
looked up by hash.

## Delivery

`gateway.py`'s `WebhookGateway` mirrors `NotificationGateway`'s
outbox shape 1:1: DB-only enqueue, a scheduled 45s dispatch tick with
`FOR UPDATE SKIP LOCKED` batching, same exponential backoff. A
subscription auto-disables after 10 consecutive failures.

## Signing

Stripe's exact scheme (`signing.py`): header
`X-Integrations-Signature`, `t=<unix_ts>,v1=<hex_hmac>`, HMAC-SHA256
over `timestamp.body`, 5-minute tolerance.

## SSRF guard

`url_safety.py` — not in the original issue text. `target_url` is
clinic-supplied and the server POSTs to it directly, so it's checked
at subscription create/update *and* again immediately before every
dispatch (a hostname can be repointed after creation). Requires
`https`, rejects any hostname or IP literal that resolves to a
private, loopback, link-local, reserved, or multicast address.

## Tenancy

Every query filters by `clinic_id`; a cross-clinic subscription id
404s rather than 403s, matching the rest of the repo's convention.

## Constraints

Own Alembic branch (`integrations`), rooted on core `"0001"` — no FK
into another module's tables (`webhook_subscriptions`/
`webhook_deliveries` FK only to `clinics.id`, which lives on the
unlabeled/core chain).

See [`./permissions.md`](./permissions.md) and
[`./events.md`](./events.md) for the full detail, and
`backend/app/modules/integrations/CLAUDE.md` for the design rationale.
