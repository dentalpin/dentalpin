---
module: leads
last_verified_commit: dd2611ce
---

# Leads

**Leads** is the queue of enquiries that arrived from your website contact
form (or that the front desk typed in by hand) and that do **not** match a
patient you already have.

> **Enquiries from existing patients do not appear here.** When the phone or
> the email already belongs to one of your patients, DentalPin adds a
> call-back to **Recalls** instead, with the enquiry text in the recall note.
> Check Recalls before assuming the form is not working.

It is an optional module: an administrator activates it from
**Settings → Modules**. Once active, **Leads** appears in the sidebar for
everyone with permission to see it.

## Screens

- [Lead queue](./screens/leads.md) — the card list, the status filter and the
  convert drawer.
- [Web form settings](./screens/intake-settings.md) — the daily limit, today
  volume and the intake key.

## Quick reference

| Action | Required permission |
|---|---|
| View the lead queue | `leads.read` |
| Add, edit, discard or convert a lead | `leads.write` |
| See the daily limit and the intake key | `leads.settings.read` |
| Change the daily limit, rotate or disable the intake key | `leads.settings.write` |

By default dentists can read the queue; assistants and receptionists can also
work it; only administrators see the settings page.

## Good to know

- **The daily limit and the intake key are configured in Settings →
  Integrations → **Website form** (*Formulario web*), not on the queue page.
- **Converting a lead creates the patient record.** Marking a lead as
  *Converted* by hand does not — see [the queue page](./screens/leads.md).
- **Leads are never deleted.** *Discarded* is the way to take one out of the
  way, and a *converted* lead keeps the link to the patient it produced.
- When an enquiry matches an existing patient nothing is lost: the call-back is
  waiting in Recalls.