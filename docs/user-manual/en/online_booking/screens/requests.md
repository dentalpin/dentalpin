---
module: online_booking
screen: requests
route: /online-booking
related_endpoints:
  - GET /api/v1/online_booking/requests
  - GET /api/v1/online_booking/requests/count
  - GET /api/v1/online_booking/requests/{request_id}/patient-suggestions
  - POST /api/v1/online_booking/requests/{request_id}/accept
  - POST /api/v1/online_booking/requests/{request_id}/reject
  - GET /api/v1/patients
related_permissions:
  - online_booking.read
  - online_booking.write
  - agenda.appointments.write
  - patients.read
  - patients.write
  - agenda.appointments.read
  - agenda.cabinets.read
related_paths:
  - backend/app/modules/online_booking/frontend/pages/online-booking/index.vue
last_verified_commit: f44dbd9
---
# Online requests

The menu shows the number of confirmed requests awaiting a decision. Review the date, reason and status. Select **Accept** on a confirmed request to open the form. To create an appointment, choose a professional, an optional cabinet and duration (initially the configured duration for the reason). Select a suggested patient matching the phone or email, search for one, or create one after reviewing the editable prefilled contact details. Select **Create appointment**.

To reject it, provide a message sent by email. If the slot is occupied, refresh the list; if the request is still pending, reject it and ask the patient to submit a new request for another time.

Creating and confirming a request checks the configured professional's appointments and holds; accepting checks the professional and cabinet you choose. Agenda permits overlapping appointments; if a later appointment occupies the slot, the next booking decision rejects the conflict.

Administrators can open **Public page settings** to enable booking and configure the responsible professional, URL, start interval, booking window, minimum notice and ordered visit reasons with Spanish and English names, duration and active status. Deactivate old reasons to preserve existing requests. Upload a PNG, JPG or SVG logo (up to 1 MB), or enter an HTTPS URL; an uploaded image takes precedence. Save before selecting **View public page**. Manage holidays and closures under Clinic hours, Special dates.
