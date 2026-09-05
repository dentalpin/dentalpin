# Content-Security-Policy — inventory and rollout (issue #355)

The app holds health data and, until ADR 0023 lands, auth tokens are
readable by JS — preventing XSS *is* the defence. CSP is the
defence-in-depth layer; this doc is the inventory the policy is derived
from and the rollout it follows.

## Where the policy lives

`frontend/server/middleware/csp.ts` (Nitro), **not** the Caddyfile:

- the e2e job runs the production build *without* Caddy, so a Nitro
  header is the only way CI enforces the same policy prod ships;
- the policy needs the runtime API origin (`NUXT_PUBLIC_API_BASE_URL`)
  for `connect-src` and `report-uri`, which Caddy doesn't know.

Caddy keeps its minimal `frame-ancestors 'self'` header (applies to API
responses too). A document therefore carries two CSP headers in prod;
browsers enforce the intersection, which is what we want.

Mode is `NUXT_CSP_MODE`:

| value | header | used where |
|---|---|---|
| `off` (default) | none | dev |
| `report` | `Content-Security-Policy-Report-Only` | prod rollout (`docker-compose.prod.yml` default) |
| `enforce` | `Content-Security-Policy` | e2e job; prod once reports are clean |

Only HTML documents get the header — `/_nuxt/*` assets and `/api/*`
passthroughs are skipped.

## Inventory (production build, 2026-09-05)

Rendered `/login` from `nuxt build` output, then grepped:

| what | count | policy consequence |
|---|---|---|
| `<script type="application/json" id="__NUXT_DATA__">` | 1 | data, not executed — no directive needed |
| `<script type="module" src="/_nuxt/…" crossorigin>` | 1 | `script-src 'self'` |
| plain inline `<script>` (Nuxt bootstrap / config) | 2 | **needs `'unsafe-inline'`** or nonces — see gap below |
| `<style id="nuxt-ui-colors">` + one more `<style>` | 2 | `style-src 'unsafe-inline'` |
| `style="…"` attributes | 2 on /login, 58 components repo-wide | `style-src 'unsafe-inline'` (attributes can't be nonced) |
| external `src=`/`href=` origins | 0 | `default-src 'self'` holds |
| inline `on*=` handlers | 0 | nothing to allow |
| API + copilot SSE | `fetch()` to the API origin | `connect-src 'self' <api origin>` |
| avatars / uploads / QR previews | `data:` and `blob:` URLs | `img-src 'self' data: blob:` |
| icons | pre-bundled (`icon.clientBundle`), no runtime CDN | `'self'` |
| docs portal (`NUXT_PUBLIC_DOCS_URL`) | opened as a link/new tab | not a resource load; no directive |

Resulting policy (see the middleware for the source of truth):

```
default-src 'self'; script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:;
font-src 'self' data:; connect-src 'self' <api-origin>;
worker-src 'self' blob:; frame-ancestors 'self'; base-uri 'self';
form-action 'self'; object-src 'none'; report-uri <api-origin>/api/v1/security/csp-report
```

## The known gap: `script-src 'unsafe-inline'`

Nuxt emits two inline bootstrap scripts whose content varies per
deployment, so static hashes don't work. Closing this needs per-response
**nonces** injected into Nuxt's own render (`nuxt-security` does exactly
this via the `ssr:html` hook, or a small custom module using the same
hook). That is a deliberate second step: it adds a dependency to a
security-critical path and changes how every inline script is rendered,
so it deserves its own PR after Report-Only has run in prod for a while
and the *rest* of the policy is proven clean. Everything except inline
scripts is already strict.

## Rollout

1. **Report-Only in prod** — `NUXT_CSP_MODE=report` (the compose
   default). Violations POST to `/api/v1/security/csp-report`, which
   logs one structured `WARNING` line per report
   (`dentalpin.csp` logger): `grep "csp violation"` in the backend logs.
2. Tighten what the reports show (a forgotten external font, a
   `blob:` worker…), keep the directives minimal.
3. **Enforce** — flip to `NUXT_CSP_MODE=enforce` once a week of reports
   is empty. CI already enforces: the e2e job runs with `enforce` and
   `tests/e2e/csp.spec.ts` fails on any "Refused to …" console line on
   the login page and the dashboard, so a regression fails the PR, not
   the clinic.
4. Nonces for `script-src` (separate PR, see above).

## References

- `frontend/server/middleware/csp.ts`
- `backend/app/core/security/router.py`
- `frontend/tests/e2e/csp.spec.ts`
- `Caddyfile`; issues #355, #351, #353; ADR 0023
