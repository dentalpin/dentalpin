# Changelog

## Unreleased

- fix(#1101): public availability checks the booking window in the clinic timezone before resolving hours, so a day far outside it (e.g. `9999-12-31`) answers an empty list instead of a 500.
- fix(#1044): accepting a booking for a new patient now requires a surname, matching the patients schema, so the created patient can be edited afterwards.
- Serve the public booking page from the application itself: Nuxt page `/p/booking/{clinicId}` in the module layer (public layout, no auth, cookie-free same-origin API calls, twelve locales, ALTCHA, honeypot, branding, confirmation landing).
- Let a clinic embed the page in an iframe on its own website: new `embed_origins` setting (https origins) applied as `frame-ancestors` for that route only; new `privacy_url` setting (the form cannot be sent without it).
- `captcha.consume` raises `CaptchaInvalidError` (400) / `CaptchaReusedError` (409) instead of `HTTPException`; `BookingRoute` maps them.
- Single migration `ob_0004` for the whole public-page feature; no `logo_url`, `logo_content_type` or `logo_sanitized` columns and no re-sanitising step.
- Expose the request's `professional_id` in the inbox so reception pre-selects the configured professional on acceptance; when only a full contact name exists, splitting for "Create patient" puts everything before the last space in the first name.
- Answer with `ApiResponse` / `PaginatedApiResponse` like the rest of the API; the inbox now returns `total`, `page` and `page_size` instead of `has_more`, and the reception page and navigation badge read the typed responses.
- Move the create, confirm, accept and reject flows (and settings, inbox and suggestions) from the router into `BookingService`, following `ConsentService`; routes only parse input and domain errors (`BookingError` subclasses) map to HTTP in `BookingRoute`.
- Scope availability to the configured professional: their `schedules` hours, their active appointments and their live holds. Other professionals' appointments no longer block a slot, and each request stores the professional it was made for (`professional_id`).
- On acceptance, recheck overlaps for the professional and cabinet reception chooses (still under the shared `agenda:clinic:` lock; the hard overlap check stays in this module, #905).
- Share the agenda clinic lock and recheck conflicts on request, confirmation and acceptance.
- Configure per-reason buffers, daily and weekly quotas, per-contact active limits, all counted for the configured professional only, optional patient questions and a post-request redirect.
- Count quotas, per-contact limits and buffers for the configured professional only: other professionals' holds, accepted requests and appointments no longer use quota or widen blocked time.
- Group booking settings and provide an image preview, color picker and notice units.
- Restrict uploaded logos to bounded static PNG, JPEG or WebP images and re-encode them without metadata; serve only sanitized PNG with cache validators and restrictive security headers. External logo URLs and SVG are unsupported.
- Configure public booking rules and bilingual, ordered visit reasons in the administrator panel; check and hold the complete duration for each reason.
- Store a size-limited validated clinic logo and expose it on a public, clinic-scoped image route; reuse clinic schedule closures.

- Render the reception accept action with the primary button style.
- Highlight available dates by week and group times by morning and afternoon. Require a validated international or Spanish phone number.
- Configure public page logo, color and bilingual text from reception settings; show the requested time in confirmation and email.

- Add a standalone static public booking and confirmation widget and clinic-bound, single-use ALTCHA v2 challenges. Public request clients must now provide an ALTCHA solution.

- Reception chooses professional, optional cabinet and duration, with per-reason defaults and conflict rechecks; patient contact fields are prefilled and matching contacts suggested.
- Show a permission-scoped count of confirmed pending requests in navigation.

- Refresh locked rows before evaluating request decisions or dispatch state.

- Queue confirmation and rejection emails with the core notifications gateway (`NotificationGateway.enqueue`) inside the request transaction, so a rolled-back request sends nothing; the gateway outbox delivers after commit.
- Add the `booking_confirmation` and `booking_rejection` email types with system templates seeded by `ob_0003` for es and en (informal "tú", no medical data). The ten other locales (ar, de, fr, hi, hu, it, pl, pt, ta, te) hold English copy pending translation.
- Remove the module's own SMTP delivery, encrypted mail outbox and worker; a confirmation still queued when its request is no longer pending is cancelled by the cleanup job.

- Add paginated reception inbox with explicit patient selection, acceptance and rejection.
- Exclude expired requests from the inbox and refuse decisions after expiration.

- Add optional, disabled-by-default online booking requests for one clinic calendar.
- Add transaction-scoped booking locks and recheck active agenda appointments.
- Add expiring confirmation tokens, reception decisions and retention cleanup.
- Add shared pseudonymous abuse counters.
- Document the booking and agenda overlap responsibilities in issue #905.
