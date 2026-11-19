---
last_verified_commit: 0000000
---
# Standalone online booking widget

This directory builds a static, self-hosted booking and confirmation page; it does not use the DentalPin Nuxt application. Node 22 and the committed lock file are required:

```sh
npm ci --ignore-scripts
npm test
npm run build
```

Deploy the generated `dist/` files to the root of the HTTPS booking origin. Edit **dist/config.js** for the target environment: set `clinicId` to the clinic UUID, `clinicName`, an HTTPS `privacyUrl`, and `language` (`es` or `en`). The public logo URL, accent color and Spanish/English title and introduction are configured in the staff inbox by users with `online_booking.settings`. The committed UUID and blank privacy URL are intentionally non-operational. The widget requires a functioning privacy URL and an enabled clinic. Set the module's authenticated `public_url` to this page's exact HTTPS URL: emails append the confirmation token in a URL fragment. Build artifacts and configuration are not credentials; do not put secrets in them.

The page may be linked directly or embedded with an iframe from the clinic website:

```html
<iframe src="https://reservas.araquedental.es/" title="Solicitar cita" width="100%" height="900" loading="lazy"></iframe>
```
 The server must send a CSP `frame-ancestors` allowing only the approved clinic web origins and the booking origin itself; do not set `X-Frame-Options: DENY` or `SAMEORIGIN` if cross-origin embedding is required. The current self-hosted ALTCHA widget uses a local bundled script, injected styles and blob workers; configure CSP appropriately and test it in the target deployment. Do not load libraries from a CDN. Set `Referrer-Policy: no-referrer` and do not log request bodies, tokens, query strings or contacts.

Proxy only these exact paths under the same origin, using a clinic UUID allowlist and method restrictions:

- `GET /api/v1/online_booking/public/{clinic_id}/config`
- `GET /api/v1/online_booking/public/{clinic_id}/availability?day=YYYY-MM-DD` or `?from_day=YYYY-MM-DD&days=1..31`
- `GET /api/v1/online_booking/public/{clinic_id}/challenge`
- `POST /api/v1/online_booking/public/{clinic_id}/requests`
- `POST /api/v1/online_booking/public/{clinic_id}/confirm`

Deny other API paths and methods, including encoded bypasses. The page uses same-origin fetch without cookies or CORS. ALTCHA v2 is required for request creation: challenges expire after ten minutes, are bound to the clinic, and successfully consumed challenges cannot be replayed. This changes the public `requests` contract: existing integrations must obtain and solve the challenge and include the `altcha` payload. Confirmation is an explicit POST initiated by the visitor; merely opening a link cannot confirm.

The backend must trust forwarded addresses only from its known proxy; enforce HTTPS, size and rate limits at the perimeter as well. Test the complete proxy configuration and iframe before deployment. Nothing in this directory deploys to Plesk or changes DNS.
