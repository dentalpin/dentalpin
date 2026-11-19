# Online booking module

- Optional and removable; depends on agenda, schedules, patients and notifications.
- Disabled by default; v1 books for one configured professional per clinic.
- Public endpoints use a clinic identifier and never accept clinical notes.
- Staff settings and decisions require module permissions and a clinic context.
- Business logic lives in `BookingService` (pattern of `ConsentService`); routes parse input and `BookingRoute` maps `BookingError` subclasses to HTTP. Responses use `ApiResponse` / `PaginatedApiResponse`.
- The `/online-booking` reception page uses the private API and clinic timezone.
- The confirmed-request accept action uses the solid primary button style.
- Acceptance additionally checks patient and agenda write permissions.
- Availability is that of the professional configured in the settings: their `schedules` hours, their active appointments and their live holds. Other professionals' appointments never block. Each request stores that professional (`professional_id`).
- Unconfirmed holds expire after ten minutes; confirmed holds end at decision or start.
- Booking and agenda writers use the shared transaction-scoped clinic lock from `agenda.locks`.
- Booking rechecks under the lock on request, confirmation and acceptance. Request and confirmation check the request's professional; acceptance checks the professional and cabinet reception chooses (same professional or same cabinet). Agenda itself does not reject overlaps (#905); a later agenda write can still create one.
- Confirm tokens are random, hashed at rest, one-use, and transmitted in URL fragments.
- Emails go through `NotificationGateway.enqueue` in the caller's transaction (types `booking_confirmation`, `booking_rejection`, `force_send`, email channel only); the core outbox delivers after commit. The module has no SMTP, outbox or worker of its own.
- System email templates are seeded by `ob_0003` (es, en; English copy for the other ten locales pending translation). Clinics may override them per locale.
- The confirmation link is in the queued message context until delivery; cleanup cancels unsent confirmations of closed requests.
- The installed module schedules expiry, 30-day deletion and 90-day contact erasure.
- The caller must provide a confirmation page that submits the token from the fragment.
- Expose only explicit public paths on the perimeter; never expose staff routes.
- Tests require isolated synthetic PostgreSQL, never patient data or real credentials.

- The independent `public_widget/` builds static assets for same-origin public APIs. ALTCHA v2 is mandatory for requests; see its README for the exact public proxy allowlist and iframe CSP.

- Public appearance fields are configured through the permission-gated reception settings. Availability supports a bounded 31-day range; phone is required and normalized to E.164.
