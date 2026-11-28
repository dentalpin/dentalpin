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
last_verified_commit: 64eb2ee
---
# Online requests

The menu shows the number of confirmed requests awaiting a decision. Review the date, reason and status. Select **Accept** on a confirmed request to open the form. To create an appointment, check the professional (preselected from the request when still available), an optional cabinet and duration (initially the configured duration for the reason). Select a suggested patient matching the phone or email, search for one, or create one after reviewing the editable prefilled contact details (a single full name is split at its last space: everything before it is the first name). Select **Create appointment**.

To reject it, provide a message sent by email. If the slot is occupied, refresh the list; if the request is still pending, reject it and ask the patient to submit a new request for another time.

When you create a new patient, the first name and last name are both required, as on the patient record. A request name that is not exactly two words stays whole in the first name, with the last name empty for you to complete.

Creating and confirming a request checks the configured professional's appointments and holds; accepting checks the professional and cabinet you choose. Agenda permits overlapping appointments; if a later appointment occupies the slot, the next booking decision rejects the conflict.

Administrators can open **Public page settings** to enable booking and configure the responsible professional, URL, start interval, booking window, minimum notice and ordered visit reasons with Spanish and English names, duration and active status. Deactivate old reasons to preserve existing requests. Upload a static PNG, JPG or WebP logo of up to 512 KB and 1024 × 1024 pixels. Metadata is removed when saving. Enter the privacy-policy URL (https) and, if you embed the page in your website, the websites allowed to embed it; the page address is shown under those fields (details in [Public booking page](booking-page.md)). Save before selecting **View public page**. Manage holidays and closures under Clinic hours, Special dates.

In Settings, configure rules, per-reason buffers and daily, weekly and contact limits. Empty limits are unlimited. Limits and buffers apply only to the responsible professional's own requests and appointments. Choose whether to ask about existing patients and allow a comment; the form asks patients not to include medical information. The optional redirect URL must use HTTPS.

Creating a patient while accepting a request does not send the generic patient welcome message.
