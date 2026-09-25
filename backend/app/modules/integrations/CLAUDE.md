# integrations module

Webhook subscriptions (REST Hooks) for third-party automations — issue
#65. Phase 1: subscription CRUD, outbox-backed delivery with
retry/backoff/auto-disable, Stripe-style HMAC signing, eight working
triggers, stable per-event `event_id`, API tokens, and a
token-authenticated public data-read API. Zapier/Make/n8n apps and the
admin UI are follow-up PRs, not in this module yet.

## What it does

Admin-authenticated CRUD under `/api/v1/integrations/webhooks/
subscriptions` and `/api/v1/integrations/tokens` (JWT +
`require_permission`, gated behind `integrations.subscriptions.read`/
`.write` and `integrations.tokens.read`/`.write`). A clinic subscribes
to one or more event types with a target URL; the module signs and
delivers a JSON payload to that URL whenever a subscribed event fires.

Token-authenticated public data-read API under `/api/v1/integrations/
public/` — no JWT, authenticated by `Authorization: Bearer dp_...`,
rate-limited per token (60/min + 1000/day, `X-RateLimit-*` headers),
clinic-scoped off the token's `clinic_id`. `GET /public/ping` is the
token-introspection auth test (no scope); every authenticated request
stamps the token's `last_used_at`; `GET /public/patients` accepts
format-tolerant exact-match `phone`/`email`/`national_id` params (the
search-or-create find primitive, issue #65 §5; ported from PR #348).

Every payload carries `occurred_at`. Since Phase 2, each delivery also
carries a stable `event_id` (same id across every subscription that
matched one bus event publish — dedupe key, issue #65 §1) and there is
a frozen sample payload per supported trigger in `sample_payloads/`.

## Outbox

`WebhookDelivery` is both the outbox queue row and the audit record
for one delivery attempt — same split as
`notifications.models.CommunicationMessage`. `gateway.py`'s
`WebhookGateway` mirrors `NotificationGateway`'s shape 1:1: `enqueue_
for_event` is DB-only (no network I/O, so a rolled-back publisher
transaction queues nothing), the scheduled `dispatch_outbox` tick
(every 45s) sends with `FOR UPDATE SKIP LOCKED` batching and commits
before each network call so no row lock is held across I/O. Backoff:
`min(60 * 2**(attempts-1), 3600)`, same formula as
`CommunicationMessage`. A subscription auto-disables after
`MAX_CONSECUTIVE_FAILURES` (10) consecutive delivery failures —
`CommunicationMessage` has no equivalent, since it tracks per-message
terminal state, not a per-subscriber circuit breaker.

## Signing

`signing.py` — Stripe's exact scheme. Header
`X-DentalPin-Signature`: `t=<unix_ts>,v1=<hex_hmac>`. Signed string
is `f"{timestamp}.{payload}"` over the raw body bytes (never a
re-serialized copy). 5-minute tolerance on verify. A receiver already
carrying a Stripe webhook verifier can reuse it unmodified, minus the
header name.

## Secrets

`WebhookSubscription.secret_encrypted` is Fernet-derived-from-
`SECRET_KEY` (`app.core.email.encryption`) — the 5th consumer of that
scheme (SMTP password, Verifactu PFX password, `whatsapp_kapso`'s API
key and webhook secret, now this). A second encryption key wouldn't
meaningfully shrink blast radius over `SECRET_KEY` already signing
every JWT, so this reuses the existing scheme rather than adding one.
The plaintext secret is
generated server-side (`secrets.token_urlsafe(32)`) and returned
**once**, in the create response only (`WebhookSubscriptionCreated`) —
never logged, never returned again, only decrypted internally to sign
a delivery.

## SSRF guard (`url_safety.py`)

Not in the original issue scoping — `target_url` is clinic-supplied
and the server POSTs to it directly, so it needed the same treatment
as any other server-side-request-forgery surface. Two checkpoints:
`validate_new_url` runs at subscription create/update (`service.py`,
not a Pydantic validator — the check needs to `await` the event
loop's own resolver, which a validator can't do) — requires `https`,
resolves the hostname, rejects private/loopback/link-local/reserved/
multicast addresses (covers `169.254.169.254` cloud metadata,
`127.0.0.1`, RFC1918, etc.), and rejects a raw IP literal in those
ranges directly. `validate_before_dispatch` runs again in
`client.post_webhook`, immediately before every send — a hostname can
be repointed after the subscription was created, so validating only
once at creation doesn't fully cover it; re-checking narrows the
window rather than fully closing it (httpx still re-resolves when it
actually connects — a TOCTOU gap, not a real DNS-rebinding defense).
`client.py` also sets `follow_redirects=False` explicitly, so a
receiver can't bounce a validated request to an unvalidated internal
URL via a 3xx.

## Tenancy

Every `WebhookSubscription`/`WebhookDelivery` query filters on
`clinic_id`. `_get_owned_subscription` (router.py) 404s rather than
403s on a cross-clinic subscription id, same as the rest of the repo's
convention for not confirming another clinic's row exists.

## API tokens

`ApiToken.token_hash` is SHA-256 of the plaintext (fixed 64 hex
chars), not the `Fernet`/`bcrypt` scheme used elsewhere in this
module/repo — deliberate, not an inconsistency. It's never decrypted
back out (unlike the webhook signing secret), so Fernet is wrong; it's
never interactively typed by a human, so it doesn't need bcrypt's slow
salted hash either — it needs a fast, indexable lookup by hash.
Plaintext is `dp_` + `secrets.token_urlsafe(32)` (the prefix is for
secret-scanning tools, same idea as Stripe's `sk_`/GitHub's `ghp_`),
shown once on creation, never stored/returned again. Revocation
mirrors `WebhookSubscription`'s own `disabled_at`/`disabled_reason`
shape (`revoked_at`/`revoked_reason`, soft, not delete). `scopes` is
validated against a closed catalog (`SUPPORTED_TOKEN_SCOPES` in
`triggers.py`, same pattern as `SUPPORTED_EVENT_TYPES`) at create time.
The public data-read API (`public.py`) and the MCP module (`mcp`) are the
consumers of those token scopes. Both authenticate through the single
shared entry point `IntegrationsService.authenticate_token`, which enforces
the per-token fixed-window rate limit (60/min + 1000/day) and stamps
`last_used_at` on every successful auth; `public.py` surfaces the
`X-RateLimit-*` headers and maps the shared `RateLimitError` to 429,
while the MCP middleware returns its own 429 JSON. The public API enforces
scopes per-endpoint via `require_scope()`; the MCP server translates the
same scopes into RBAC grants and lists tools accordingly.
Single-process rate limiting — documented limitation.

## Dependencies

`manifest.depends = ["patients"]`. `agenda` is deliberately NOT
listed even though `appointment.completed` is published there —
consuming an event doesn't require depending on its publisher module
(same as `patient_timeline`'s own precedent), and `agenda` is a core
module (`auto_install=True`, `removable=False`) always present
regardless.

## Lifecycle

- `installable=True`, `auto_install=False` (repo policy for optional
  modules), `removable=True`.
- Own Alembic branch (`integrations`), rooted on core `"0001"` —
  `int_0001` (initial schema: `webhook_subscriptions`,
  `webhook_deliveries`), `int_0002` (adds `api_tokens`).

## CHANGELOG

See `./CHANGELOG.md`.
