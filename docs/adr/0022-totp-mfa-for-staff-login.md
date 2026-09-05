# 0022 — TOTP second factor for staff login, and a 12-character password floor

- **Status:** proposed
- **Date:** 2026-09-05
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** security, auth

## Context

An external implementer's audit (issue #354) found no second factor for
ordinary staff login — the only one in the tree guards public quote links
(ADR 0006), a different threat — and a password policy of 8 characters +
one letter + one number (`backend/app/core/auth/service.py`,
`validate_password_strength`). The app holds health data; a phished or
reused staff password is a full-clinic breach.

Two decisions are bundled because they share the login surface. The
password floor ships immediately (the PR carrying this ADR); TOTP follows
once the ADR is accepted.

## Decision

1. **Password floor is 12 characters**, letter + number check kept.
   Length beats composition (NIST SP 800-63B); no forced rotation, no
   special-character rule. Applies wherever a password is *set*
   (first-run setup, admin-created users, invite `set-password`, own
   password change) — never at login, so existing accounts keep working
   until their next change. The demo seed (`demo1234`) is unaffected by
   design: it is only ever *logged in with*.
2. **TOTP (RFC 6238) as the staff second factor**, implemented in core
   auth (login is core, not a module):
   - **Enrolment**: `POST /auth/mfa/totp/enroll` returns a provisioning
     URI (`otpauth://totp/DentalPin:<email>?secret=…&issuer=DentalPin`)
     rendered as a QR client-side; `POST /auth/mfa/totp/confirm` with one
     valid code activates it and returns **10 single-use recovery codes**
     (shown once, stored as bcrypt hashes).
   - **Login**: `/login` with a correct password on an MFA-enabled
     account returns `202 {"mfa_required": true, "mfa_token": …}` — a
     short-lived (5 min) JWT of type `mfa` bound to the user and
     `token_version` — instead of a session. `POST /auth/mfa/verify`
     with `{mfa_token, code}` (TOTP or recovery code) mints the normal
     access/refresh pair. ±1 step (30 s) window; the last accepted TOTP
     counter is stored to reject replay inside the window.
   - **Policy**: mandatory for `admin`; opt-in for other roles; a
     per-clinic `settings.mfa_required_for_all` toggle (admin-only)
     makes it mandatory for every member — members without MFA are
     redirected to enrolment on next login, not locked out.
   - **Recovery**: an admin can reset a member's MFA
     (`DELETE /auth/mfa/users/{id}`), forcing re-enrolment; audit-logged.
     Admins cannot reset their own — that is what recovery codes are
     for; a solo-practice DB-level reset runbook lives in
     `docs/workflows/`.
   - **Storage**: `user_mfa_totp(user_id PK, secret_encrypted,
     confirmed_at, last_counter, created_at)` +
     `user_mfa_recovery_codes(id, user_id, code_hash, used_at)` on the
     core linear chain. The secret is Fernet-encrypted at rest via
     `app.core.email.encryption` (the project-wide scheme).
   - **Rate limits**: `/mfa/verify` shares the login limiter's key
     (10/min per identity); five consecutive failures on one
     `mfa_token` invalidate that token.
   - **Sessions**: enabling or resetting MFA bumps `token_version`, so
     every existing session re-authenticates through the new gate.

## Consequences

### Good

- Phished/reused passwords stop being a full-clinic breach for admins by
  default, and for everyone the clinic opts in.
- No new dependency: the QR uses the `qrcode` package Verifactu already
  ships, and RFC 6238 is ~40 lines of HMAC-SHA1 verified against the
  RFC test vectors — one fewer supply-chain surface for a security
  primitive (revisit `pyotp` only if step/drift configuration grows).
- The `mfa_token` step leaves `/login` semantics for non-MFA users
  unchanged (200 + tokens), so existing clients and the e2e login
  fixture keep working.

### Bad / accepted trade-offs

- A second login step for admins on every new device. Mitigation: the
  7-day refresh token — MFA is checked at *login*, not at refresh.
- Recovery codes are a shared-secret fallback; losing both the
  authenticator and the codes needs another admin or the runbook.
- WebAuthn/passkeys are deliberately out (#354 says so) — the
  `mfa_token` handshake is method-agnostic, so `POST /auth/mfa/webauthn/*`
  slots in next to TOTP later.

## Alternatives considered

- **Email / SMS OTP** — email is the account's own recovery channel
  (circular); SMS is SIM-swap-prone and needs #231's gateway. Rejected as
  the primary second factor; fine as an *additional* method later.
- **Step-up MFA on sensitive actions** (e.g. before a patient-data
  export) — valuable, orthogonal to login MFA; a follow-up.
- **Enforce 12 characters at login too** — would lock out accounts with
  8–11 character passwords with no self-service path. Rejected; the floor
  applies on set/change only.

## How to verify the rule still holds

- `backend/tests/test_auth.py::test_password_floor_is_12` — an
  11-character password is rejected on the setup path;
  `test_setup_weak_password` keeps covering composition.
- When TOTP lands: `tests/test_auth_mfa.py` covers enrol → confirm → 202
  handshake → verify (TOTP and recovery), replay rejection, admin reset,
  and the mandatory-for-admin gate.

## References

- `backend/app/core/auth/service.py` — `validate_password_strength`,
  `MIN_PASSWORD_LENGTH`
- `backend/app/core/auth/router.py` — `/login`, `/refresh`,
  `/set-password`
- Issue #354; ADR 0006 (public-link second factor); ADR 0023 (cookie
  auth + refresh rotation — the login surface this shares)
