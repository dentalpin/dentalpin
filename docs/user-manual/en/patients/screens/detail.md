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
  - GET /api/v1/periodontogram/patients/{patient_id}/snapshots
  - GET /api/v1/periodontogram/patients/{patient_id}/timeline
  - GET /api/v1/periodontogram/patients/{patient_id}/draft
  - POST /api/v1/periodontogram/patients/{patient_id}/draft
  - GET /api/v1/periodontogram/snapshots/{snapshot_id}
  - GET /api/v1/periodontogram/snapshots/{snapshot_id}/indices
  - PATCH /api/v1/periodontogram/snapshots/{snapshot_id}/teeth/{tooth_number}
  - PATCH /api/v1/periodontogram/snapshots/{snapshot_id}/teeth/{tn}/sites/{site_code}
  - POST /api/v1/periodontogram/snapshots/{snapshot_id}/close
  - DELETE /api/v1/periodontogram/snapshots/{snapshot_id}
related_permissions:
  - patients.read
  - patients.write
  - periodontogram.read
  - periodontogram.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/[id].vue
  - backend/app/modules/periodontogram/frontend/components/PeriodontogramView.vue
  - backend/app/modules/periodontogram/frontend/components/PeriodontogramChart.vue
  - backend/app/modules/periodontogram/router.py
last_verified_commit: 6dde74fc546d6bf48bc251b41ab49fc0a27fa7e1
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

<a id="periodontogram"></a>

## Periodontogram (diagnosis sub-view)

> Requires `periodontogram.read`. Optional module — activate it from
> *Admin → Modules → Periodontogram → Install*.

The **Periodontogram** sub-tab lives inside *Clinical → Diagnosis*,
next to the odontogram. It bundles the timeline slider, the indices
banner, and the SEPA-style chart for both arches. In-app help links
land here via the `#periodontogram` anchor.

### At a glance

```
┌────────────────────────────────────────────────────────────────────┐
│ [Amber banner — only when viewing a past snapshot] .............. │
│                                                                    │
│ [Date slider]──●──────●──●─────────[Now]                           │
│                                                                    │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ [Pill] Draft / Closed · 23 Mar 2026                            │ │
│ │ BoP 18%  ·  PI 12%  ·  CAL 1.8mm  ·  Pockets ≥5mm: 3           │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ UPPER                                                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  SEPA table (9 rows × 16 teeth)                               │ │
│  │  Teeth — buccal face                                          │ │
│  │  Teeth — palatal face (vertical flip)                         │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ LOWER                                                              │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │  Teeth — lingual face (vertical flip)                         │ │
│  │  Teeth — buccal face                                          │ │
│  │  SEPA table                                                   │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                    │
│ [Sticky bottom bar — drafts only]                                  │
│  [⏳ Saved]      [Discard draft]    [Close session ✓]              │
└────────────────────────────────────────────────────────────────────┘
```

### Empty state

If the patient has no snapshots and no active draft, the sub-tab
shows a card with a **Start exam** button. Clicking it creates a
pre-filled draft and loads the full view.

### Cell-level editing

1. **Site (probing, margin, bleeding, plaque, suppuration).** Click
   any dot on a tooth or any sub-cell on the *Bleeding / Plaque /
   Gingival margin / Probing* rows. A modal opens with five fields.
2. **Tooth (mobility, prognosis, furcation, keratinized gingiva).**
   Click on the matching row for the tooth. A modal opens with the
   per-tooth fields. Furcation rows only appear for molars.

Edits autosave after a 600 ms debounce window. The indicator at the
bottom-left of the chart shows the state: *Saving…* / *Pending
changes* / *Saved*.

### Visual heatmap

Probing depth colours each dot:

| Probing | Colour |
|---------|--------|
| 0–3 mm | Green |
| 4 mm | Yellow |
| 5–6 mm | Orange |
| ≥ 7 mm | Red |

Bleeding and plaque add small overlay markers on the dot (red and
blue respectively).

### History

The top slider is the same component used by the odontogram: each
node is a closed snapshot. Selecting a past date raises an amber
banner and disables every input. *Return to current* reloads the
most recent snapshot or the active draft.

### Close session

From the sticky bottom bar, *Close session* opens a confirmation
modal with an optional clinical note field. On confirm:

1. Pending in-flight edits are flushed to the backend.
2. The SEPA indices are computed and frozen on the snapshot.
3. The snapshot status flips to `closed`, the slider gains a new
   node, and every input becomes read-only.

### Discard draft

*Discard draft* deletes every value entered into the active draft.
It is not reversible — the modal warns before confirming.

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
- Each payment in the timeline has a row menu: **Assign to quote…**
  (moves an on-account deposit to the chosen quote and, if it has
  issued invoices, applies it) and **Refund**. The menu shows only the
  actions your role allows.

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

Below the channels, one switch per message type (appointment reminder,
quote sent, invoice sent, recall reminder…). Turning a type off blocks it
on every channel, manual sends from staff included; the clinic-wide
on/off for each type stays in notification settings.

## Groups

The **Groups** card lists the clinic-local tags assigned to the
patient (e.g. *vip*, *recall-risk*). With
`patient_segments.write` you can assign existing groups, create new
ones inline, or remove them. Groups are labels only — no points, no
expiry.

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
