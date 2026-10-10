# Public-route audit (T1): scoping rules per surface

Cross-cutting tech reference for the four unauthenticated surfaces. Every
rule cites file + route; the adversarial tests in
`backend/tests/test_public_route_scoping.py` pin the failure shapes.
Status shapes below are the CURRENT contract — uniform-404 is the rule
for new surfaces (§5); existing 401/403/409/410/423/429 shapes stay
until a dedicated slice changes them openly, never silently.

## 1. Budget public links (`budget/public_router.py`, ADR 0006)

Mounted under `/api/v1/budget/public/budgets/{token}/`. No staff auth,
no `require_permission`: the UUID token plus a per-token HS256 session
cookie are the auth.

| Route | Failure shape |
|---|---|
| `GET .../meta` | unknown token → 404 `Budget link not found` (`public_router.py:176`) |
| `POST .../verify` | unknown token → 404 (`:267`); decided → 409 (`:269`); locked → 423; expired → 410; window-limited → 429; wrong value / wrong method → 401 (`:281`-`:288`, codes from `workflow.py:verify_public_access`) |
| `GET ...` (detail) | unknown token → 404 (`:306`); no/wrong cookie → 401 `verification_required` (`:312`); expired → 410 (`:331`) |
| `POST .../accept`, `POST .../reject` | same 404/401 as detail; decided → 409 (`:355`, `:491`) |
| `GET .../pdf/signed` | same 404/401; not accepted/signed → 404 (`:409`, `:427`) |

Scoping rule: token lookup (`BudgetService.get_by_public_token`,
`service.py:458`) carries no clinic filter by design — the token is the
access factor. Every downstream query re-scopes through
`budget.clinic_id` (`:338`, `:366`, `:429`, `:497`); the `/meta`
display read binds `:id = budget.clinic_id` on the core `clinics`
table only (no patient lookup since #539). Cookie `bdg_session_{token}` is path-scoped to the token's own
prefix (`:96`) and binds `tok` to the URL token (`:110`), so a cookie
for budget A reads as 401 on budget B. Lockout is permanent after 10
failed attempts (`workflow.py`, `public_locked_at`); rate limits are
slowapi (`5/15min` per token, `20/hour` per IP) and only active in
production.

## 2. Notifications push-subscribe (`notifications/public_router.py`)

Mounted under `/api/v1/notifications/public/push/subscribe/{token}`.
UUID token, 24 h TTL, single use (`push.py:PushSubscribeTokenService`).

| Route | Failure shape |
|---|---|
| `GET ...` (validate) | unknown / used / expired → 404 `Invalid or expired subscribe token` (`:48`); VAPID unconfigured → 503 (`:52`) |
| `POST ...` (redeem) | unknown / used / expired / patient-gone → 404 (`:92`, via `LookupError`); malformed subscription → 422 (`:94`) |

Scoping rule: the token row carries `clinic_id` + `patient_id` from mint
time; redemption atomically consumes single-use (`UPDATE ... WHERE
used_at IS NULL`, `push.py:182`) and re-validates the patient inside the
token's clinic (`push.py:171`). The receipt is `{subscribed: true}`
only — no ids leak (`:81`). Same-token and cross-patient replays both
read 404.

## 3. Leads intake (`leads/public_router.py`)

`POST /api/v1/leads/public/intake`. No clinic context by design (the
website holds no JWT); the `X-Lead-Key` secret is the auth. Full
coverage already lives in `tests/modules/leads/test_intake.py`; this
section pins the contract, not the cases.

- Missing / unknown / inactive key → one generic 401 (`:48`,
  `:107`-`:111`). Plaintext never stored or logged — only its SHA-256,
  including as the rate-limit bucket (`:60`).
- Outcome uniformity (D12): new lead, recall queued, opted-out match
  and honeypot all answer the same 201 `{"received": true}` (`:39`,
  `:103`, `:138`) — the endpoint is not a patient oracle.
- Abuse floor: declared body cap 413 (`:73`), per-key + per-IP slowapi
  limits (production only), per-clinic daily cap 429 with counter
  committed before rejection (`:121`), honeypot writes nothing (`:101`).
- Scope: key hash resolves `clinic_id` (`service.py:339`); settings,
  matching and inserts all filter by it (`service.py:231`, `:135`).

## 4. Integrations public API (`integrations/public.py`)

`/api/v1/integrations/public/` with `dp_`-prefixed bearer tokens
(SHA-256 stored, shown once, revocable, no expiry). Full coverage in
`tests/modules/integrations/test_public_api.py`; contract pinned here.

- Missing / malformed / unknown / revoked token → 401 with
  `WWW-Authenticate: Bearer` (`:114`, `:121`, `:131`); missing scope →
  403 (`:152`); per-token 60/min + 1000/day windows → 429 (`:93`).
- `GET /patients` and `GET /patients/{patient_id}` scope every query by
  the token's `clinic_id` (`:208`, `:265` via `PatientService`); a
  foreign-clinic id reads 404, never 403 — no cross-clinic oracle.
- Response is the `PublicPatientResponse` subset only (no billing,
  photos, notes, lifecycle flags; `schemas.py:121`).

## 5. Standing checklist for new public surfaces

1. Token is the auth: random ≥128-bit, hashed at rest, single display.
2. Invalid / expired / foreign scope all read the SAME shape (404 with
   a generic detail for resource-bound tokens; generic 401 for
   key-shaped auth). Never let the status distinguish the reason.
3. Every query filters by the resolved `clinic_id` (L1) — including
   inside helpers the route calls. An id-only query is a security bug.
4. Success responses carry no ids, no cross-tenant data, no reason
   strings an attacker can learn from.
5. Abuse floor documented: rate limits (noting slowapi is
   production-only), caps, honeypots, atomic counters where floods must
   stay visible.
6. Adversarial tests land with the surface: enumeration (foreign id),
   injection (malformed input), expiry, replay, revocation.
