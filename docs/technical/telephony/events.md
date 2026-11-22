---
module: telephony
last_verified_commit: 0000000
---

# telephony — events

## Published

| Event | When | Payload |
|-------|------|---------|
| `call.ringing` | inbound/outbound call starts ringing | clinic_id, call_log_id, call_id, event, direction, from_number, to_number, patient_id (null when unmatched) |
| `call.answered` | call answered | same |
| `call.ended` | call ended (answered earlier) | same |
| `call.missed` | explicit missed event, or ended-without-answer on inbound | same |
| `call.unknown_caller` | alongside an inbound `call.ringing` when no patient matched | same |

All published with `db=` (transactional, ADR 0019). No bundled
subscriber — `patient_timeline` / `integrations` may subscribe without
importing this module.

## Subscribed

_This module subscribes to no events._
