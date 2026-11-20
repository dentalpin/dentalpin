---
module: gdpr
screen: access-log
last_verified_commit: fdbdaf8d
route: /settings/people/patient-access-log
related_permissions:
  - gdpr.access_log.read
  - gdpr.retention.write
related_endpoints:
  - GET /api/v1/gdpr/access-log
  - GET /api/v1/gdpr/access-log/users
  - GET /api/v1/gdpr/access-log/csv
  - GET /api/v1/gdpr/access-log/retention
  - PUT /api/v1/gdpr/access-log/retention
---

# Patient access log

Open a patient and select **Access log** to see who accessed the record,
when, and what they opened. Open **Settings → People → Patient access
log** to review accesses by staff member.

Choose start and end dates to download a CSV. Both dates are inclusive
and follow the clinic's timezone. Repeated views of the same type of
resource are grouped into fixed ten-minute periods. Downloads and
portability exports are recorded individually.

Your role needs `gdpr.access_log.read` to see this screen or export CSV.
The clinic keeps entries for five years by default. With
`gdpr.retention.write`, you can change the period on the same settings
page. The daily cleanup applies the new period to existing records.
