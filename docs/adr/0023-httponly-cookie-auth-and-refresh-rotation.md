# 0023 — HttpOnly cookie sessions with rotating, revocable refresh tokens

- **Status:** proposed
- **Date:** 2026-09-05
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** security, auth, frontend

## Context

Issue #353 (external audit, the most substantive finding). Verified on
main today:

- `frontend/app/composables/useAuth.ts` stores **both** tokens in
  JS-readable cookies (`useCookie('access_token')`,
  `useCookie('refresh_token')`, `secure` only in prod, `SameSite=Lax`,
  7-day `maxAge` on both) and `useApi` reads the access cookie to build
  `Authorization: Bearer …` on every call; on a 401 it calls
  `auth.refresh()` and retries once.
- The refresh token is a **stateless JWT** (`create_refresh_token`,
  7 days). `POST /auth/refresh` decodes it, checks `type == "refresh"`,
  the user is active and `token_version` matches, and mints a new pair.
  Nothing invalidates the *old* refresh token: it stays valid until
  expiry unless `token_version` is bumped for the whole user (which logs
  out every device).
- The copilot SSE stream (`useCopilotStream.ts`) is `fetch()` with the
  same `Authorization` header — EventSource can't set headers.
- The e2e fixture (`frontend/tests/e2e/_fixtures.ts`) logs in via the
  API and **pins the `access_token` cookie by hand**.

Risk: any XSS (no CSP yet — #355) reads a 7-day refresh token from
`document.cookie`, and a stolen refresh token can be replayed for its
whole lifetime with no server-side way to revoke just that token.

## Decision

1. **Tokens become `HttpOnly; Secure; SameSite=Lax` cookies set by the
   backend**, never readable by JS:
   - `/auth/login`, `/auth/refresh`, `/auth/mfa/verify` (ADR 0022) and
     `/auth/set-password` respond with `Set-Cookie` for
     `dp_access` (path `/`, TTL = access TTL 15 min) and `dp_refresh`
     (path `/api/v1/auth/refresh`, TTL = refresh TTL) — the refresh
     cookie is only ever sent to the one endpoint that needs it.
   - The JSON body keeps returning the access token **during a one-release
     transition** so third-party API clients aren't broken; the frontend
     stops reading it. `useApi` sends `credentials: 'include'` and drops
     the `Authorization` header for same-origin calls; the backend's
     bearer dependency accepts **either** the header or the `dp_access`
     cookie (header wins), so scripts, the Zapier public API (dp_ tokens,
     unaffected) and the SSE `fetch()` keep working unchanged.
   - `/auth/logout` clears both cookies **and** revokes the refresh
     token (below).
2. **Refresh rotation with server-side revocation** (per-token, not
   per-user):
   - New core table `auth_refresh_tokens(id/jti PK, user_id, family_id,
     issued_at, expires_at, revoked_at, replaced_by, user_agent_hash,
     last_ip)`. Every refresh JWT carries `jti` and `family_id`.
   - `/auth/refresh`: verify JWT → look up `jti` → must be unrevoked and
     unexpired → **revoke it, mint a new one in the same family**
     (`replaced_by` set), return the new pair. Presenting an
     **already-revoked** jti is treated as theft: the whole family is
     revoked (classic rotation-with-reuse-detection) and the user must
     log in again.
   - `token_version` stays as the "log out everywhere" hammer
     (password change, MFA enable/reset); rotation is the scalpel.
   - Logout revokes the presented family; an admin "sign out all
     sessions" for a member revokes all families for that user.
   - Expired rows are pruned by the existing scheduler (daily job in
     core, not a module).
3. **CSRF posture**: `SameSite=Lax` cookies + the existing custom
   `X-Requested-With`-style requirement is *not* enough for the
   state-changing endpoints once auth is a cookie, because Lax still
   sends cookies on top-level GET navigations. Decision: **double-submit
   token** — `/auth/login` also sets a non-HttpOnly `dp_csrf` cookie;
   `useApi` echoes it as `X-CSRF-Token` on every non-GET; a core
   dependency rejects unsafe methods whose header ≠ cookie. Public
   endpoints (webhooks, `dp_` bearer API, public quote links) are
   exempt by construction — they never carry the session cookie.
4. **Same-origin is a requirement**, not an option: cookies + CSRF
   assume the API is served under the app's origin (the Caddy `/api/*`
   route already does this; `docker-compose.yml` dev keeps
   `localhost:3000` → `localhost:8000` cross-origin, so dev needs
   `SameSite=Lax` + CORS `credentials: true` on the backend for
   `http://localhost:3000` — already the case for the header flow).

## Consequences

### Good

- XSS can no longer exfiltrate a session; the refresh token never
  leaves the `/auth/refresh` path; a stolen refresh token is
  single-use and its reuse burns the family.
- Per-device sign-out becomes possible (families ≈ devices).
- API clients using bearer headers (Zapier tokens, scripts, the e2e
  fixture's direct API calls) are untouched.

### Bad / accepted trade-offs

- `useApi`, `useAuth`, the SSE composable and the e2e fixture all
  change; the fixture moves from "set cookie by hand" to "call `/login`
  through the page context so the browser stores the HttpOnly cookies".
  One PR touches ~6 files on the frontend and 3 on the backend.
- A DB write per refresh (one row insert + one update every 15 min per
  active session) — negligible at clinic scale, and it's what makes
  revocation possible.
- The transition release returns tokens in the body *and* sets cookies;
  the body field is removed one release later (documented in the
  CHANGELOG and the public-API docs).

## Alternatives considered

- **Keep bearer-in-JS, add CSP only** (#355) — CSP is defense-in-depth,
  not a substitute; one missed inline handler and the 7-day token walks.
- **`token_version` bump on every refresh** — logs out every other
  device of the user on each refresh; correct but unusable.
- **Stateless rotation (embed previous jti in the new token)** — can't
  revoke on reuse without state; the table is the point.
- **Opaque session ids instead of JWTs** — clean, but a bigger rewrite
  (every dependency decoding claims); JWT access + stateful refresh is
  the incremental path.

## How to verify the rule still holds

- `tests/test_auth_cookies.py` (with the implementation): login sets
  `HttpOnly` cookies and the body still carries the token in the
  transition release; a request with only the cookie is authenticated;
  refresh rotates (old jti rejected, family revoked on reuse); logout
  revokes; CSRF header mismatch on POST is 403.
- e2e: the login fixture no longer writes `document.cookie`; a grep for
  `useCookie('access_token'` / `useCookie('refresh_token'` in
  `frontend/app` returns nothing.

## References

- `frontend/app/composables/useAuth.ts`, `useApi.ts`
- `backend/app/core/auth/router.py` — `/login`, `/refresh`, `/logout`
- `backend/app/core/auth/service.py` — `create_refresh_token`
- `backend/app/modules/copilot/frontend/composables/useCopilotStream.ts`
- `frontend/tests/e2e/_fixtures.ts`
- Issue #353; ADR 0022 (MFA handshake shares `/login`); issue #355 (CSP)
