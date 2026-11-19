---
module: online_booking
screen: requests
route: /online-booking
related_endpoints:
  - GET /api/v1/online_booking/requests
  - POST /api/v1/online_booking/requests/{request_id}/accept
  - POST /api/v1/online_booking/requests/{request_id}/reject
  - GET /api/v1/patients
related_permissions:
  - online_booking.read
  - online_booking.write
  - agenda.appointments.write
  - patients.write
related_paths:
  - backend/app/modules/online_booking/frontend/pages/online-booking/index.vue
last_verified_commit: 0000000
---
# Online requests

Review the date, reason and confirmation status. To accept a confirmed request, find and select an existing patient or enter a first and last name to create one. To reject it, provide a message sent by email. If the slot is occupied, refresh the list; if the request is still pending, reject it and ask the patient to submit a new request for another time.
