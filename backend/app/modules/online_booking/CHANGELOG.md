# Changelog

## Unreleased

- Queue encrypted confirmation and rejection emails in the request transaction and send only after commit.

- Add paginated reception inbox with explicit patient selection, acceptance and rejection.
- Exclude expired requests from the inbox and refuse decisions after expiration.

- Add optional, disabled-by-default online booking requests for one clinic calendar.
- Add transaction-scoped booking locks and recheck active agenda appointments.
- Add expiring confirmation tokens, reception decisions and retention cleanup.
- Add shared pseudonymous abuse counters and TLS-only email delivery.
- Document the concurrent agenda writer limitation tracked by issue #905.
