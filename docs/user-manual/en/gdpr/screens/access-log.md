---
module: gdpr
last_verified_commit: 0000000
route: /settings/people/patient-access-log
permissions: [gdpr.audit.read]
---

# Patient access log

Open a patient and select **Access log** to see who accessed the record,
when, and what they opened. Open **Settings → People → Patient access
log** to review accesses by staff member.

Choose start and end dates to download a CSV. Both dates are inclusive
and follow the clinic's timezone. Repeated views of the same type of
resource are grouped into fixed ten-minute periods. Downloads and
portability exports are recorded individually.

Your role needs `gdpr.audit.read` to see this screen or export CSV.
The clinic keeps entries for five years by default. With
`gdpr.retention.write`, you can change the period on the same settings
page. The daily cleanup applies the new period to existing records.
