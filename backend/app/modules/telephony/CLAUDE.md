# telephony module

CTI gateway (issue #64, phase 1): a public HMAC-verified webhook accepts
**normalized call events** from any source (PBX call-flow, Zapier/Make
recipe), numbers are normalized to E.164, callers are matched against
patients, every call lands in `telephony_call_logs`, and `call.*` events
go on the bus. The screen-pop is polling-based: the `callPop` client
plugin toasts new ringing calls for any logged-in user with
`telephony.calls.read`; `/calls` is the receptionist's log + live view.
Community, removable.

## Public API

Routes at `/api/v1/telephony/`:

| Method | Path | Auth |
|---|---|---|
| GET/PUT | `/settings` | `telephony.settings.read` / `.write` |
| GET | `/status` | `telephony.calls.read` (pop-poll gate probe) |
| GET | `/calls` | `telephony.calls.read` |
| GET | `/calls/active` | `telephony.calls.read` (the pop poll) |
| PUT | `/calls/{id}/note` | `telephony.calls.write` |
| POST | `/events/{clinic_id}` | **PUBLIC** — per-clinic HMAC signature |

## Ingest contract (documented — breaking to change)

`POST /events/{clinic_id}`, body signed with `X-DentalPin-Signature`
(`t=<ts>,v1=<hmac>` over the raw bytes, `app.core.webhooks.signing` —
a Stripe webhook signer works unmodified):

```json
{
  "event": "call.ringing" | "call.answered" | "call.ended" | "call.missed",
  "call_id": "<provider-call-id>",
  "direction": "inbound" | "outbound",
  "from_number": "600 11 22 33",
  "to_number": "+34910000000",
  "agent_extension": "203",
  "started_at": "…", "answered_at": "…", "ended_at": "…",
  "duration_seconds": 47,
  "provider": "webhook"
}
```

The clinic id lives in the URL (the PBX is configured with the full
path); authenticity is the HMAC — a guessed id without the secret is
401. Unusable events (unknown `event`, empty `call_id`) are
**accepted-and-ignored** so a misconfigured PBX never retry-storms.

## Semantics

- One `CallLog` row per `(clinic, provider, call_id)` — created on the
  first event, updated by the rest.
- `call.ended` on an inbound call that was never answered records
  `missed` (some PBXs don't send an explicit missed event).
- Numbers normalize via `phonenumbers` with the clinic's
  `default_country`; unparseable input is kept verbatim (a call log with
  an odd number beats a dropped event).
- Matching: SQL narrows on the last digits, Python confirms on the full
  normalized value (patient phone and caller both through
  `normalize_number` with the clinic's `default_country`, so a foreign
  number or an extension that only shares the tail links nobody, #973);
  **exactly one** match links `patient_id`, multiple matches
  deliberately link none (phase 1 sends the user to the
  pre-filtered patient search instead of guessing a household member).

## Events emitted

`call.ringing` / `call.answered` / `call.ended` / `call.missed`, plus
`call.unknown_caller` alongside a ringing event with no patient match.
All published with `db=` (transactional). Payload: (clinic_id,
call_log_id, call_id, event, direction, from_number, to_number,
patient_id|null). No bundled subscriber — patient_timeline /
integrations may subscribe without importing this module.

## Dependencies

`manifest.depends = ["patients"]` — the caller-match import and the
`patient_id` FK. Signing comes from core (`app.core.webhooks`).

## Secrets

`tel_` + `token_urlsafe(32)`, Fernet at rest, shown once on the save
that generated it, rotation via `PUT /settings {"rotate_secret": true}`.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch `telephony` (`tel_0001`). Roundtrip uninstall test
  drops only `telephony_*`.

## Gotchas

- **The ingest payload is a public contract** — clinics build PBX
  call-flows/Zaps against it; version, don't rename.
- The pop is polling (15s) by design in phase 1 — a realtime channel is
  the documented upgrade path in issue #64 §3, not something to bolt on
  here ad hoc. The plugin gates the poll on `GET /status` (re-checked
  every 10 min) so unconfigured clinics don't pay the 15s cadence, and
  caps its seen-ids set at 200.
- Two simultaneous *first* events of one call race past the SELECT; the
  savepoint + `IntegrityError` adopt-the-winner path in
  `ingest_event` is what keeps the loser from 500ing — don't "simplify"
  it away.
- Vendor adapters (aircall/3cx/twilio_voice) belong in their own
  community modules that POST into this gateway, not in this module.

## CHANGELOG

See `./CHANGELOG.md`.
