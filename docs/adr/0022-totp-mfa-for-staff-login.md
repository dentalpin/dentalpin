# 0022 — TOTP second factor for staff login, and a 12-character password floor

- **Status:** accepted
- **Date:** 2026-09-05
- **Amended:** 2026-11-18 (#887)
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
password floor shipped in #380. The earlier opt-in-only TOTP proposal was
deferred in September. This amendment accepts the clinic policy in #887.

## Decision

1. **Password floor is 12 characters**, letter + number check kept.
   Length beats composition (NIST SP 800-63B); no forced rotation, no
   special-character rule. Applies wherever a password is *set*
   (first-run setup, admin-created users, invite `set-password`, own
   password change once one exists — there is no self-service change
   endpoint today) — never at login, so existing accounts keep working
   until their next change. The demo seed (`demo1234`) is unaffected by
   design: it is only ever *logged in with*.
2. **Staff TOTP lives in core auth**, using PyOTP and an authenticator app.

### Policy and enrollment

Each clinic chooses off, optional, required for all staff, or required for
selected roles. The account is global, so a requirement in any of the user's
clinics applies at sign-in. Off disables voluntary enrollment for staff
without an enabling policy. A staff member with an active factor continues to
verify at sign-in.

An unenrolled user subject to a requirement completes setup after password
validation and before receiving a session. An optional user can start setup
from their profile after re-entering their password. The API supplies a QR
image and manual setup key. A valid code confirms enrollment and returns ten
single-use recovery codes once. The account stores only hashes of these
random, high-entropy codes.

### Sessions and recovery

Login and invitation completion return a `202` challenge when MFA is
required. An opaque, hashed, five-minute challenge is bound to the user,
purpose and token version. It can only complete its own auth flow. Completing
it consumes the challenge and issues the normal ADR 0023 cookies and tokens.
The renewal endpoint requires a new sign-in for an unenrolled account subject
to a mandatory policy. An already-issued access token can run to its expiry.

The verifier accepts the current TOTP interval and one interval of drift on
either side. It serializes verification per account and rejects a counter at
or below the last accepted counter. Five failed code attempts lock the account
for 15 minutes across challenges, in addition to the request limiter.

An optional user can disable MFA after proving the password and a valid
authenticator or recovery code. Reset from the staff settings requires an
administrator in every clinic where the user is a member. It revokes the
user's existing sessions and recovery codes, then requires re-enrollment at
the next sign-in. Enabling and disabling MFA also revoke the former sessions.

### Storage and audit

The TOTP secret and any pending enrollment secret use Fernet encryption with
a key dedicated to MFA. The key can be rotated independently of the JWT
signing key. See [Staff MFA operations](../workflows/staff-mfa.md).

The core records enable, disable, reset and failed verification events in a
durable audit table and publishes `auth.2fa_enabled`, `auth.2fa_disabled`,
`auth.2fa_reset` and `auth.2fa_failed`. A CLI recovery reset has no staff actor, so its `actor_id` is null.
The payload otherwise carries account and actor
IDs, the clinic ID when a reset has clinic context, and a timestamp.

## Consequences

- A password by itself cannot establish a new staff session when a second
  factor applies. Password-only login retains the existing response for
  accounts without a factor or mandatory policy.
- Setup and recovery become part of clinic operations. The deployment needs
  a dedicated key before activating the policy, and staff need their
  authenticator or recovery codes.
- Public patient links keep their own verification. WebAuthn, SMS, trusted
  devices and machine credentials are outside this change.

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
- `backend/tests/test_auth_mfa.py` covers enrollment, session issuance,
  replay and expiry, scoped reset, recovery, rate limiting and key rotation.

## References

- `backend/app/core/auth/service.py` — `validate_password_strength`,
  `MIN_PASSWORD_LENGTH`
- `backend/app/core/auth/router.py` — `/login`, `/refresh`,
  `/set-password`
- Issue #354; ADR 0006 (public-link second factor); ADR 0023 (cookie
  auth + refresh rotation — the login surface this shares)
- [PyOTP documentation](https://pyauth.github.io/pyotp/)
- [Fernet and MultiFernet](https://cryptography.io/en/stable/fernet/)
