---
module: sms_gateway
last_verified_commit: 0f333000
---

# sms_gateway — overview

SMS delivery for notifications through pluggable provider backends
(issue #231). Community, removable. The module registers an SMS
adapter into the notifications channel gateway; the gateway's
consent, opt-out, rate-limit and outbox machinery applies unchanged
with `channel=sms`.

## What it is

Admin-authenticated endpoints under `/api/v1/sms_gateway/` (JWT +
`sms_gateway.*` RBAC, admin role only). One settings row per clinic
selects the provider backend and stores its credentials encrypted;
`/test` dry-runs the configuration without sending anything.

Routes:

- `GET /api/v1/sms_gateway/settings` — masked provider config
- `PUT /api/v1/sms_gateway/settings` — select provider, store credentials, toggle
- `POST /api/v1/sms_gateway/test` — honesty dry-run (sends nothing)

## Providers

v1 ships the `log` placeholder only: sends are recorded in the server
log and reported successful so the queue → dispatch flow runs end to
end without spending money. The UI and docs label it "not sending" —
nobody should install this expecting SMS to go out. Twilio and other
providers register as new backends under the same adapter later; a
selected-but-unimplemented provider fails honestly at send time.

## Data model

Single table `sms_gateway_settings`, `clinic_id`-scoped and indexed:
provider key, Fernet-encrypted account SID / auth token, from-number,
active flag. Migration `smg_0001_initial` on own Alembic branch
(`sms_gateway`), no `depends_on`.

## Tenancy

Every query filters by `clinic_id`. Credentials are per-clinic
secrets; responses expose `has_*` booleans only.

## Constraints

Own Alembic branch (`sms_gateway`); `manifest.depends =
["notifications"]`. No agent tools in v1. Adapter registers on
activate and unregisters on uninstall.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.
