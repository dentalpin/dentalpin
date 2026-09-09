# Changelog — telephony module

## Unreleased

- feat(i18n): Arabic (`ar`) locale for the module's frontend layer.
- fix(#64): the three post-merge review follow-ups from #349 — the first-event unique-constraint race adopts the winner's row via a savepoint instead of failing; the `callPop` poll is gated on a new cheap `GET /status` probe (10-min re-check) so unconfigured clinics don't pay the 15s cadence; the plugin's seen-ids set is capped at 200.

- feat(#64): initial release — phase 1 of the CTI design: HMAC-verified
  inbound event webhook (any PBX / Zapier), E.164 normalization,
  caller→patient matching, persistent call log with live view and
  polling screen-pop toast, `call.*` bus events, settings page with
  show-once signing secret.
