---
module: gdpr
last_verified_commit: 47a008bcc85677e4e45c93b34d7a7e1525e86f29
---

# gdpr — events

Per-module slice of [`docs/events-catalog.md`](../../events-catalog.md)
(auto-generated). Update both files when adding or removing events.

## Published

| Event | When | Payload keys |
|-------|------|--------------|
| `gdpr.request.created` | a data-subject request is created | `clinic_id`, `request_id`, `patient_id`, `request_type` |
| `gdpr.request.status_changed` | a DSR status changes (received → in_progress → completed/rejected) | `clinic_id`, `request_id`, `patient_id`, `from_status`, `to_status`, `changed_by` |
| `gdpr.consent.granted` | a consent is recorded | `clinic_id`, `consent_id`, `patient_id`, `purpose` |
| `gdpr.consent.withdrawn` | a consent withdrawal is appended (new row, `granted=false`) | `clinic_id`, `consent_id`, `patient_id`, `purpose` |
| `gdpr.erasure.executed` | a partial erasure committed; announcement only, published after commit (#546) | `clinic_id`, `patient_id`, `request_id`, `erased_categories`, `retained_categories` |
| `gdpr.breach.reported` | a data-breach report is created | `clinic_id`, `breach_id`, `affected_people` |

All events are published by the gdpr service layer after the DB commit
succeeds — including `gdpr.erasure.executed` (#546): the in-transaction
work moved to the erasure contributor registry (ADR 0038), so the event
is a pure announcement with no transactional subscribers. Optional
subscribers react to rights lifecycle without importing gdpr models.

## Subscribed

_This module does not subscribe to any events._

## Adding a new event

1. Add the constant to `backend/app/core/events/types.py` (`EventType`).
2. Publish from a service method, after the DB commit succeeds.
3. Add the row to the table(s) above.
4. Run `python backend/scripts/generate_catalogs.py` to refresh the
   global catalog.