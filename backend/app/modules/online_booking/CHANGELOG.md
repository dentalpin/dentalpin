# Changelog

## Unreleased

- Share the agenda clinic lock and recheck active appointments and live holds on request, confirmation and acceptance.

- Render the reception accept action with the primary button style.

- Reception chooses professional, optional cabinet and duration, with per-reason defaults and clinic-wide conflict rechecks; patient contact fields are prefilled and matching contacts suggested.
- Show a permission-scoped count of confirmed pending requests in navigation.

- Refresh locked rows before evaluating request decisions or dispatch state.

- Queue encrypted confirmation and rejection emails in the request transaction and send only after commit.

- Add paginated reception inbox with explicit patient selection, acceptance and rejection.
- Exclude expired requests from the inbox and refuse decisions after expiration.

- Add optional, disabled-by-default online booking requests for one clinic calendar.
- Add transaction-scoped booking locks and recheck active agenda appointments.
- Add expiring confirmation tokens, reception decisions and retention cleanup.
- Add shared pseudonymous abuse counters and TLS-only email delivery.
- Document the booking and agenda overlap responsibilities in issue #905.
