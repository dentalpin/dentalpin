# Changelog — integrations module

## Unreleased

- Initial module (Phase 1 of issue #65, narrow first slice approved by
  Ramón 2026-08-21): webhook subscription CRUD, outbox-backed delivery
  with retry/backoff/auto-disable, Stripe-style HMAC-SHA256 signing,
  and one working trigger (`patient.created`).
- Added second Phase 1 trigger `appointment.completed`, per Ramón's
  2026-08-21 email (supersedes the single-trigger PR #246 slice).
  `manifest.depends` now includes `agenda`.
- Added `ApiToken` model + admin CRUD (`GET/POST /tokens`, `POST
  /tokens/{id}/revoke`), also per that email. Server-side generated
  (`secrets.token_urlsafe(32)`), shown once, SHA-256-hashed at rest
  (not Fernet/bcrypt — see `models.ApiToken` docstring). No consumer
  endpoint yet — the public data-read API is a follow-up PR.
- SSRF guard on `target_url` (`url_safety.py`) — not in the original
  issue scoping. Validated at subscription create/update and again
  immediately before every dispatch (a hostname can be repointed after
  creation). Rejects non-`https` schemes and any hostname/literal that
  resolves to a private, loopback, link-local, reserved, or multicast
  address, including the cloud metadata IP. `client.py` also sets
  `follow_redirects=False` so a validated request can't be redirected
  to an unvalidated internal URL.
- Added `CLAUDE.md` and this file.
- Added the round-trip uninstall test required for `removable=True`
  modules (`test_uninstall_roundtrip.py`, `alembic_roundtrip` marker).
