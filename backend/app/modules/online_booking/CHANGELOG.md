# Changelog

## Unreleased

- fix(#1044): accepting a booking for a new patient now requires a surname, matching the patients schema, so the created patient can be edited afterwards.

- Answer with `ApiResponse` / `PaginatedApiResponse` like the rest of the API; the inbox now returns `total`, `page` and `page_size` instead of `has_more`, and the reception page and navigation badge read the typed responses.
- Move the create, confirm, accept and reject flows (and settings, inbox and suggestions) from the router into `BookingService`, following `ConsentService`; routes only parse input and domain errors (`BookingError` subclasses) map to HTTP in `BookingRoute`.
- Scope availability to the configured professional: their `schedules` hours, their active appointments and their live holds. Other professionals' appointments no longer block a slot, and each request stores the professional it was made for (`professional_id`).
- On acceptance, recheck overlaps for the professional and cabinet reception chooses (still under the shared `agenda:clinic:` lock; the hard overlap check stays in this module, #905).
- Share the agenda clinic lock and recheck conflicts on request, confirmation and acceptance.

- Render the reception accept action with the primary button style.

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
