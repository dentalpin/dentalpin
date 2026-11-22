---
module: patient_intake
last_verified_commit: 0000000
---

# First-visit intake backend

Reception issues a clinic- and patient-bound session with an immutable form
version. The form keeps the exact wording of the privacy notice, questionnaire
and four communication choices in the selected locale. Known minors need a
verified representative. Reception records the representative's verified name
and capacity.

The internal signed-submission handoff stages answers for staff review.
Reception applies selected administrative fields and validates the signed
destinations. A clinician applies selected context fields and adds reviewed
list entries. Unknown or unanswered fields preserve existing data. Duplicate
active entries and conflicting changes require staff resolution.

## Consent

The intake workflow writes `patient_intake:` purposes to the GDPR ledger as
`managed` entries (the staff consent endpoint refuses further manual entries for
them) in the same transaction as the delivery projection and cancellation of pending
messages. Provenance links the ledger to the signed submission and immutable
form, with attribution. The time of signing differs from the time of review.
An older form cannot override a newer recorded consent decision. Delivery
already in progress may have left the system.

Enrolled patients require verified contact bindings for email, WhatsApp and
SMS, and affirmative purpose consent for appointment reminders. Other
channels are outside this consent policy and are blocked for enrolled patients. Clinic
adapter selection, notification preferences and `do_not_contact` still apply.
The bindings are keyed digests scoped to clinic and patient. A destination or
server secret change requires renewed verification. The default form enables
WhatsApp and email with SMS disabled. Clinics use existing notification settings
to select the manual WhatsApp adapter.

## Evidence and retention

The follow-up based on #906 adds the public tablet page, trusted signature and
separately authorized clinical and communication PDFs. Configuration defaults
to clinical retention of at least five years, communications retention while
active plus three years, discarded staging for 30 days, and unsigned sessions
for 24 hours. This backend implements the staging cleanup. PDF retention is
applied by the follow-up.
