# Changelog — telephony module

## Unreleased

- fix(#964): an outbound call is matched on the number dialled (`to_number`), not on the clinic's own line. It used to link nobody (or whichever patient record held the clinic's number), publish `call.unknown_caller` and pop up as an incoming call. `call.unknown_caller` and the call pop are now inbound-only.
- fix(#973): the caller match is confirmed on the whole normalized number, as the module contract says, not on the last nine digits again. A foreign number or a six-digit extension sharing a patient's tail used to link that patient.
- fix(#986): an inbound call that ends unanswered (stored as `missed`) is published as `call.missed`, as `docs/technical/telephony/events.md` documents; it used to go out as `call.ended`. A `call.ended` after an explicit `call.missed` stays `call.ended`.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.
- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- feat(i18n): Arabic (`ar`) locale for the module's frontend layer.
- fix(#64): the three post-merge review follow-ups from #349 — the first-event unique-constraint race adopts the winner's row via a savepoint instead of failing; the `callPop` poll is gated on a new cheap `GET /status` probe (10-min re-check) so unconfigured clinics don't pay the 15s cadence; the plugin's seen-ids set is capped at 200.

- feat(#64): initial release — phase 1 of the CTI design: HMAC-verified
  inbound event webhook (any PBX / Zapier), E.164 normalization,
  caller→patient matching, persistent call log with live view and
  polling screen-pop toast, `call.*` bus events, settings page with
  show-once signing secret.
