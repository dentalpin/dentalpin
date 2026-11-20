# Online booking module

- Optional and removable; depends on agenda, schedules, patients and notifications.
- Disabled by default; v1 supports one shared calendar per clinic.
- Public endpoints use a clinic identifier and never accept clinical notes.
- Staff settings and decisions require module permissions and a clinic context.
- The `/online-booking` reception page uses the private API and clinic timezone.
- The confirmed-request accept action uses the solid primary button style.
- Acceptance additionally checks patient and agenda write permissions.
- Schedules supply opening hours; active appointments and live holds block slots.
- Unconfirmed holds expire after ten minutes; confirmed holds end at decision or start.
- Booking and agenda writers use the shared transaction-scoped clinic lock from `agenda.locks`.
- Booking rechecks all active clinic appointments and live holds on request, confirmation and acceptance; agenda itself does not reject overlaps (#905). A later agenda write can still create one.
- Confirm tokens are random, hashed at rest, one-use, and transmitted in URL fragments.
- Emails are encrypted in a module-owned transactional outbox; workers only send committed rows.
- The production delivery path uses TLS SMTP without logging recipients or token URLs.
- The installed module schedules expiry, 30-day deletion and 90-day contact erasure.
- The caller must provide a confirmation page that submits the token from the fragment.
- Expose only explicit public paths on the perimeter; never expose staff routes.
- Tests require isolated synthetic PostgreSQL, never patient data or real credentials.
