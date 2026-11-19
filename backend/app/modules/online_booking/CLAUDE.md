# Online booking module

- Optional and removable; depends on agenda, schedules, patients and notifications.
- Disabled by default; v1 supports one shared calendar per clinic.
- Public endpoints use a clinic identifier and never accept clinical notes.
- Staff settings and decisions require module permissions and a clinic context.
- Acceptance additionally checks patient and agenda write permissions.
- Schedules supply opening hours; active appointments and live holds block slots.
- Unconfirmed holds expire after ten minutes; confirmed holds end at decision or start.
- The clinic advisory lock coordinates only this module's cooperating transactions.
- Agenda writers do not acquire it; a concurrent agenda write can race (#905).
- Confirm tokens are random, hashed at rest, one-use, and transmitted in URL fragments.
- The production delivery path uses TLS SMTP without logging recipients or token URLs.
- The installed module schedules expiry, 30-day deletion and 90-day contact erasure.
- The caller must provide a confirmation page that submits the token from the fragment.
- Expose only explicit public paths on the perimeter; never expose staff routes.
- Tests require isolated synthetic PostgreSQL, never patient data or real credentials.
