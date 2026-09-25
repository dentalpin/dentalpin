---
module: leads
screen: leads
route: /leads
related_endpoints:
  - GET /api/v1/leads/
  - POST /api/v1/leads/
  - PATCH /api/v1/leads/{lead_id}
  - POST /api/v1/leads/{lead_id}/convert
related_permissions:
  - leads.read
  - leads.write
related_paths:
  - backend/app/modules/leads/router.py
  - backend/app/modules/leads/frontend/pages/leads/index.vue
last_verified_commit: ecda1519
---

# Lead queue

The queue at **/leads** lists the enquiries that came in and matched nobody.
It is the reception desk work list: read the enquiry, call the person, convert
them into a patient or discard the card.

## The list

Each card shows the initials of the enquirer tinted by status, the name with a
status badge, the **motive** (what the call is about), the phone and the
description trimmed to one line, and — on wide screens — a **week strip with the
days they can be called** plus how long ago the enquiry arrived. Long text is
trimmed on the card; the drawer shows it in full.

| Status | Meaning |
|---|---|
| **New** | Received, nobody has called yet. |
| **Contacted** | The front desk reached out. |
| **Converted** | Became a patient from this card (the card keeps the link). |
| **Discarded** | Not going anywhere — kept for the record, never deleted. |

- The queue **opens filtered to New** — the work still to be done — so converted
  and discarded cards do not clutter it. The chip shows `Status · 1`: the filter
  is visible, not a hidden default.
- The **status filter** chips accept several statuses at once. Clear the selection
  to see *every* status, converted and discarded history included — nothing is
  ever unreachable.
- Marking a card **Contacted**, **Converted** or **Discarded** takes it out of
  the default view; switch the chip (or clear it) to find it again.
- The **search box** looks in the name, the phone and the email.

## Converting a lead into a patient

Clicking a card opens the drawer on the right. This is the whole point of the
page: you fill in the patient record while still seeing what the person asked
for.

1. **Enquiry panel** (read only) — motive, description, the week strip with the
   days and time of day they can be called, phone, email and the date it was
   received.
2. **Duplicate warning** — if a patient with the same phone already exists, an
   alert links to that record. It does not block the conversion: families share
   a phone number.
3. **Patient form** — pre-filled from the enquiry:
   - **Name** — the single name from the form is split at the **first
     whitespace**: `Marta Ruiz` becomes *Marta* + *Ruiz*, and *Marta de la
     Fuente* becomes *Marta* + *de la Fuente*. A one-word name leaves the last name
     empty for you to complete. It is a guess, so both fields stay editable.
   - **Phone** and **email** — copied exactly as they came in.
   - **Notes** — **left empty on purpose.** The motive and the call
     availability are logistics for this call, not patient data: they stay on
     the lead card and in the panel above, and are never copied into the
     patient's chart. Write there only what belongs in the record.
   - **National ID** and **date of birth** stay empty — the form does not ask
     for them.
4. **Create patient** — enabled once first name and last name both have a
   value. On success the drawer shows a confirmation with an **Open patient**
   link; you are not thrown out of the page, because the next enquiry is
   usually one click away.

If the card is already **Converted**, the drawer replaces the form with a
banner and an *Open patient* link. A lead cannot be converted twice.

## Adding a lead by hand

**Manual lead** (top of the queue, needs `leads.write`) opens a small form for
an enquiry taken over the phone: full name, phone and motive are required;
email and description are optional. Availability is a **week picker** — tap the
days they can be called and, if it matters, pick *mornings*, *afternoons* or
*evenings* (leave it at *Any time* when they did not say). There is no status
selector when creating — a brand-new enquiry is *New* by definition.

The save has **two possible outcomes**, and the message you get tells you which
one happened:

- **The person is new** — the card is saved and appears at the top of the list.
- **The phone or email already belongs to a patient** — nothing is added to
  Leads. You get a different message naming the patient, telling you that a
  call-back was added to **Recalls**. Look there: the enquiry will never appear
  in the Leads list.

A phone shared by a family can match several patients; each of them gets a
call-back, and the message names the closest match.

**Read the first line of that call-back's note before you act on it.** It says
`Web form — submitted as: …` with the name, phone and email the form actually
carried. The label is written in your clinic's own language (the one set for
clinic communications), so a Spanish clinic reads *Formulario web — enviado
como*; the enquiry's arrival fixed that wording, and older notes keep the
language they were written in. The person who filled in the form is not
necessarily the patient it landed on — a relative, a mistyped digit, or a phone
two patients share all produce a match — so if that first line is not the
patient you are looking at, treat the text below it as someone else's words and
check before cancelling, changing or recording anything clinical.

## Editing, marking and discarding

The pencil on a card opens the edit form: correct a mistyped phone, change the
motive, or move the card to *Contacted*, *Converted* or *Discarded* after the
call.

**Marking a lead as Converted here does not create a patient** and does not
link one. It only labels the card. To actually create the patient, use the
convert drawer — that is the action that writes the patient record, and it is
the only one that links the card to it.
## What the forms refuse to send

Both forms (the manual lead form and the convert drawer) validate before they
send anything, and tell you which field is wrong **in your language**:

- **Email** — must look like an address: one `@`, something before it, a domain
  with a dot (`name@example.com`). `marta@example` and `marta..ruiz@example.com`
  are refused.
- **Phone** — digits, spaces and `+ ( ) - . /` only, with at least 6 digits. On
  the convert drawer it must also fit the patient record (20 characters).
- **Required fields** — name, phone and motive on a lead; first and last name on
  a patient.
- **Date of birth** — cannot be a future date (or more than 120 years ago).

The field is highlighted with the reason, and the save is not sent. The server
validates the same payload, so anything the form accepts is not rejected later.

