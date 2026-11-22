---
module: telephony
screen: calls
route: /calls
related_endpoints:
  - GET /api/v1/telephony/calls
  - GET /api/v1/telephony/calls/active
  - PUT /api/v1/telephony/calls/{call_log_id}/note
related_permissions:
  - telephony.calls.read
  - telephony.calls.write
related_paths:
  - backend/app/modules/telephony/router.py
  - backend/app/modules/telephony/frontend/pages/calls/index.vue
last_verified_commit: f70d47ff
screenshots: []
---

# Call log

The call log lists every phone call the telephony gateway received —
matched to a patient when exactly one record owns the other party's
number: the caller on an incoming call, the number dialled on an
outgoing one.

## Live calls

Calls currently ringing or in progress appear as a banner at the top of
the page (and, for incoming calls, as a pop-up toast anywhere in the
app for staff with call access). **Open record** jumps to the matched patient; for an unknown
caller, **Search patient** opens the patient list pre-filtered by the
number.

## The list

Each row shows when the call started, the caller (linked to the patient
record when matched), the number in international format, the status
(Ringing / Answered / Ended / Missed) and the duration. Filter by status
with the selector at the top right. Staff with write access can attach a
short note to a call from the API (UI affordance coming with the recall
integration).

## Requirements

The gateway must be configured by an administrator under Settings →
Integrations → Telephony (CTI): the clinic's PBX or a Zapier/Make
automation posts call events to the clinic's webhook URL, signed with
the secret shown at setup.
