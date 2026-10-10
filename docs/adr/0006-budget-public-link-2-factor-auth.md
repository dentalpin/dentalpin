# 0006 — Budget public link two-factor authentication

- **Status:** accepted
- **Date:** 2026-04-28
- **Deciders:** Ramon Martinez
- **Tags:** security, privacy, budget, public-api

## Context

When a clinic sends a treatment budget to a patient, the patient receives
an email/SMS with a link to a public web view containing personally
identifiable information (PII): full name, treatments, prices, dates,
clinic identity. Under Spanish LOPD and EU GDPR this is sensitive
sanitary information.

Today the design contemplated a single UUID v4 token in the URL as the
sole access factor. The UUID protects against guessing (≈10³⁸ search
space), but it does **not** protect against link sharing: if the email is
forwarded, the link is pasted in WhatsApp, the URL is screenshotted, or
the patient's email account is compromised, the budget becomes visible
to whoever holds the link.

Concrete risk surfaces:

- Email forwarded to family members on a shared account.
- Browser history / cache on a shared device.
- URL pasted into messaging apps with public previews.
- Search-engine indexing if the URL leaks (mitigated separately with
  `noindex` headers, but not sufficient on its own).
- Compromise of an email account.

We need a second factor of authentication that is cheap, low-friction,
universally available to dental patients (including elderly / low
digital literacy), and does not require a separate channel that the
clinic does not already operate.

## Decision

The public budget link is protected by **two factors**:

1. **Possession factor:** UUID v4 `public_token` embedded in the URL.
2. **Knowledge factor:** a piece of patient data verified through a
   server-side endpoint, with rate limiting and lockout. The method is
   resolved deterministically at send time and stored in
   `budgets.public_auth_method`. Cascade:

   1. **`phone_last4`** — last 4 numeric digits of the patient's phone
      number. Default. Used when the patient record has a phone with
      ≥4 digits.
   2. **`dob`** — patient's date of birth, as ISO date. Used when phone
      is missing.
   3. **`manual_code`** — a 4-6 digit numeric code configured by
      reception staff at send time, hashed with bcrypt/argon2 and
      stored in `budgets.public_auth_secret_hash`. Used when both
      phone and DOB are missing. The clinic communicates this code to
      the patient **verbally**, not through the same channel as the
      link, so a compromised email does not compromise both factors.

   Per-clinic toggle `clinic.settings.budget_public_auth_disabled` (off
   by default) lets a clinic opt out and accept the risk; it sets
   `public_auth_method = "none"` for new budgets.

Successful verification issues an **HttpOnly + Secure + SameSite=Strict
cookie** scoped to `/api/v1/budget/public/budgets/<token>`, signed
with a dedicated secret `BUDGET_PUBLIC_SECRET_KEY` independent of the
global `SECRET_KEY` used for staff JWTs (hard-required in production;
dev-only fallback otherwise). TTL: 30 minutes from successful
verification. Later requests reuse the same cookie until its `exp`;
they do not issue a fresh cookie.

**Rate limiting and lockout** are enforced server-side over a new
`budget_access_logs` table:

- 5 failed attempts per token in 15 minutes → 429.
- 10 retained failed attempts **against the same budget, from any IPs** →
  `budgets.public_locked_at` is set and the token stops verifying. The
  lock is deliberately budget-wide: the token URL is a secret only the
  patient holds, so for health data a staff-recoverable lock beats a
  weaker brute-force bound. This keeps a 10-recorded-failure cap,
  bounded by the 90-day `budget_access_logs` retention, that a per-IP
  partition would remove. Recovery is staff-side:
  reception clears the lock with `unlock-public`
  (`POST /budgets/{id}/unlock-public`, `budget.write`), which nulls
  `public_locked_at` and drops the budget's retained failed-attempt rows (else
  the retained-failure counter would re-lock on the next wrong guess), so the
  existing token works again. Note the trade: clearing the counter
  also clears the evidence of those attempts, so reception can clear
  the forensic trail together with the lock; reissue (new version, new
  token, old token permanently dead) remains the answer when the link
  itself is considered burned.
- 20 `POST /verify` requests per IP per hour → 429 (`slowapi` default
  key, the remote address). This is a request counter, not a failure
  counter, so it also throttles a patient who keeps mistyping; it does
  not apply to the other public endpoints, which carry their own
  per-token or per-IP-per-minute limits.

## Consequences

### Good

- Strong protection against link-sharing leaks at zero variable cost
  (no SMS gateway).
- Universally available factors: virtually every dental patient knows
  their phone number or date of birth.
- The `manual_code` fallback gives reception an in-person/phone-call
  channel that is independent from the link's channel — meaningful 2FA.
- Independent secret (`BUDGET_PUBLIC_SECRET_KEY`) limits blast radius
  if one of the keys leaks; allows independent rotation.
- Lockout policy converts brute force into an operational signal
  (reception notified) instead of silently allowing more attempts.
- Auditable: verification attempts are initially logged with a hashed IP and
  the method attempted, and the staff unlock route writes a
  `BudgetHistory` entry identifying the actor, budget, and previous
  lock state.

### Bad / accepted trade-offs

- `unlock-public` erases the failed verification metadata and hashed IPs.
  Clearing the lock also deletes those rows: the stored method name, IP
  hash, outcome, and count are no longer recoverable afterward. The route
  records who performed the unlock, the affected budget, and the previous
  lock state in `BudgetHistory`; success rows are retained.
- Adds a small UX step for the patient before reading the budget.
  Mitigated by a mobile-first verify form with autofocus and clear
  copy.
- If the patient record has stale phone or DOB, the legitimate patient
  may fail verification and need reception to reissue. Operationally
  acceptable.
- The `manual_code` fallback depends on reception following the
  policy of communicating the code verbally. The
  `SetPublicCodeModal.vue` UI explicitly states this in copy; the
  email template never includes the code.
- Logs require a retention policy (90 days, see cron
  `purge_budget_access_logs`) to avoid unbounded growth and to comply
  with privacy expectations.
- Brute-force resistance of the 4-digit `manual_code` relies on the
  lockout, not on the search space alone.
- `/meta` answers with routing state plus the clinic fields the page
  needs (name, contacts, locale, currency) (#539). Patient identity
  (name) and budget contents (number, total, validity) stay behind the
  knowledge factor and arrive with the cookie-protected detail
  response. The contact, locale, and currency fields stay: they are
  business data, not patient data, and the page needs them before
  verification (locale switching, money formatting, call links).

## Alternatives considered

- **UUID-only (status quo of the original draft).** Rejected: does not
  defend against link sharing, which is the dominant real-world threat.
- **Random password sent in the same email.** Rejected: zero security
  gain. Compromise of the email channel exposes both factors.
- **OTP via SMS at link open.** Rejected for MVP: requires SMS gateway
  integration (Twilio/MessageBird), recurring per-message cost in EUR,
  and adds friction without commensurate benefit when phone-last-4 +
  lockout already meets the threat model. Reconsidered for v2 if
  audit data shows the current scheme insufficient.
- **DOB + phone-last-4 multi-factor.** Rejected as default: better
  search space (~3.6 × 10⁷) but doubles friction. The lockout in the
  single-factor design already makes brute force infeasible.
- **Static per-clinic password.** Rejected: not patient-specific,
  shared secret risk, no audit trail.

## How to verify the rule still holds

- Tests: `backend/tests/test_public_route_scoping.py` is the public
  budget surface's test file (the module has no in-module `tests/`
  package). It covers the unknown-token 404s, the verify cascade
  (correct value → cookie, bad value → 401, decided → 409, expired →
  410, locked → 423), a cookie minted for one budget being rejected on
  another, the `none` method needing no cookie, the minimized `/meta`
  shape (routing state plus kept clinic fields; patient identity and
  budget contents asserted absent), the budget-wide lockout total, and
  the accept/reject
  `BudgetAccessLog` rows. The production boot rules for
  `BUDGET_PUBLIC_SECRET_KEY` (required, minimum length, no blank or
  padded values) are proven in `backend/tests/test_secret_key_strength.py`.
- What the tests do and do not reach: `phone_last4` (the default method)
  is exercised end to end over HTTP, including a wrong value and the
  locked/decided/expired gates. Creating or cloning any budget executes
  the resolver, so its `phone_last4` default is exercised incidentally,
  but without a focused assertion. The clinic opt-out, `dob`,
  `manual_code`, and missing-patient arms have no coverage: no test in
  `backend/tests/` sends `method: "dob"` or `method: "manual_code"`.
  `phone_last4` and `dob` compare with `secrets.compare_digest`;
  `manual_code` is a bcrypt `checkpw` against the stored hash
  (`backend/app/modules/budget/workflow.py`). A change to the resolver
  or one of those branches must add a test to
  `backend/tests/test_public_route_scoping.py` in the same change; an
  earlier revision of this section named test files that never existed,
  which is exactly how a rule silently stops holding.
- Every data-bearing route except `/meta` and `/verify` is guarded by
  the `_require_session` dependency in
  `backend/app/modules/budget/public_router.py`. To re-check the
  surface, list the routes in that file (the public prefix moved out of
  `router.py` into `public_router.py`):
  `rg -n '_require_session' backend/app/modules/budget/public_router.py`

## References

- `backend/app/modules/budget/models.py` (Budget public_token,
  public_auth_*, public_locked_at; BudgetAccessLog; BudgetHistory for
  staff unlocks).
- `backend/app/modules/budget/workflow.py` (resolve_public_auth_method,
  verify_public_access).
- `backend/app/modules/budget/public_router.py` (public endpoints, the
  `_require_session` cookie dependency). `router.py` holds only the
  staff side, including `unlock-public`.
- `backend/app/modules/budget/tasks.py` (`purge_budget_access_logs`),
  registered as a scheduled job in
  `backend/app/modules/budget/__init__.py`.
- `docs/workflows/plan-budget-flow-tech-plan.md` §1.4, §5.2.
- `docs/workflows/plan-budget-flow.md` (patient verification step).
