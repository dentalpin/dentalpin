---
module: patients
screen: detail
route: /patients/[id]
related_endpoints:
  - GET /api/v1/patients/{patient_id}
  - PUT /api/v1/patients/{patient_id}
  - DELETE /api/v1/patients/{patient_id}
  - GET /api/v1/patients/{patient_id}/extended
  - PUT /api/v1/patients/{patient_id}/extended
related_permissions:
  - patients.read
  - patients.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/[id].vue
last_verified_commit: 829bdd25
---

# Patient detail

Dashboard-style patient view. A persistent header carries identity,
critical allergy chips and quick actions; below it sits a tab strip.
The default **Summary** tab is a modular dashboard where each block
is contributed by a different module (plans, agenda, payments,
dental chart, medical history). Every block is also a deep link —
one click reaches the detail.

## Layout

- **Sticky header** — avatar, name, age, ID, contact, critical
  allergy chips (allergy, pregnancy, anticoagulant…) and *Edit* +
  *Actions ▾* buttons (Appointment, Collect, Note, Archive). Stays
  visible while scrolling and across tabs.
- **Summary (dashboard)** — smart-cards contributed by each owning
  module via the `patient.summary.cards` slot:
  - **Active plan** *(treatment_plan)* — title, progress bar, n/m
    treatments. Click → plan detail.
  - **Next appointment** *(agenda)* — day/time/professional.
    Click → appointment.
  - **Last visit** *(agenda)* — date/time/professional of the most
    recent completed appointment; "Never visited" for a patient who
    has not been in the chair yet. Click → appointment (or the agenda
    with the patient pre-selected when there is none).
  - **Balance** *(payments)* — debt / on-account / paid. Click →
    Administration → Payments.
  - **Diagnoses** *(odontogram)* — untreated findings count.
    Click → dental chart in diagnosis mode.
  - **Medical history** *(patients_clinical)* — allergies, systemic
    diseases, medication. Click → edit history.
  - **Quick actions** *(patients)* — Appointment, Budget, Document
    and the `patient.summary.actions` slot for sibling modules
    (recalls *Set recall*, notifications, etc.).
- **Tabs** — Info, Clinical, Administration, Gallery, History. In
  Clinical and Administration the sub-nav is a pill-bar exposing all
  modes upfront (Diagnosis · Plans · Appointments · History /
  Budgets · Billing · Payments · Documents).
- **Mobile** — header condenses, cards stack to a single column and
  a sticky bottom bar surfaces the three core actions
  (Appointment · Collect · Note).

## Editing identity

> Requires `patients.write`.

1. Click the pencil icon in the summary hero, or the **Edit** button on
   the *Identity* sub-tab.
2. Update name, contact, ID document, demographics. Extended demographics
   live behind the *Identity → Extended* tab and are persisted via the
   `/extended` endpoint.
3. **Save** publishes a `patient.updated` event with the changed fields,
   so dependents (recalls, notifications, …) can react.

## Archiving a patient

> Requires `patients.write`. Patients are **never** hard-deleted.

1. Open the **⋮ More** menu in the summary hero.
2. Click **Archive patient**.
3. Confirm. The patient's `status` flips to `archived`, the row is
   hidden from default lists, and a `patient.archived` event is
   published.
4. To restore, run an SQL update on the `status` column — there is no
   in-app un-archive flow yet.

## Payments tab — "Pending to charge"

The **Administration → Payments** tab shows the patient ledger
(total paid, debt, on-account balance) and, when there is real debt,
a **Pending to charge** card at the top.

- The card lists the recently completed sessions that net payments
  haven't covered yet (FIFO).
- Total equals `clinic_receivable = earned − net_paid`.
- The **Collect X €** button opens the payment modal with the amount
  pre-filled; reception picks the method and the **Apply to** target
  (an open quote or *on account*) and confirms. On-account money
  touches neither invoices nor quotes; the modal says so.
- After the payment is recorded, the card disappears (or shrinks)
  depending on how much was collected.
- Each payment in the timeline has a row menu: **View detail**,
  **Assign to quote…** (moves an on-account deposit to the chosen
  quote and, if it has issued invoices, applies it) and **Refund**.

## Budgets tab

**Administration → Budgets** lists the patient's quotes. Quotes generated
from a treatment plan carry a "Linked to plan `<plan number>`" tag next to
their date, so reception can tell a plan quote from a standalone one.

## "Do not contact"

The `do_not_contact` flag is the operational opt-out. When enabled:

- Recalls module excludes the patient from any recall queue.
- Future outreach modules (email, SMS) MUST honour the flag.
- The patient still appears in the list and can be opened normally —
  they just won't be pestered automatically.

## Notification preferences

The summary card carries per-patient channel preferences: preferred
channel (email, WhatsApp or SMS), an SMS opt-in toggle (SMS sends only
when enabled), and the UI language. `do_not_contact` overrides
everything.

## Permissions

| You see / can do | Permission |
|------------------|-----------|
| View the detail | `patients.read` |
| Edit identity / extended | `patients.write` |
| Archive | `patients.write` |
| Sibling-module actions (recalls, notifications, …) | The sibling module's permissions. |

## Troubleshooting

- **Edit and Archive buttons are hidden.** Your role lacks
  `patients.write`. An admin can grant it via *Settings → Users → Roles*.
- **A tab I expected isn't there.** That tab is contributed by a
  sibling module (e.g. *Treatment plans*). Make sure that module is
  installed and you have its read permission.
