---
module: sistema_ts
last_verified_commit: 0000000
---

# Sistema Tessera Sanitaria (Italy)

This optional module reports the clinic's **patient invoices** to the
Sistema Tessera Sanitaria, so the expenses appear in each patient's
pre-filled tax return (730 precompilato). It sends automatically: every
paid invoice to a private person on the next run, credit notes as
refunds, voided invoices as cancellations.

Invoices to companies are not its business (they go through the SDI
module); the two are exclusive by law.

## Screens

Both pages live under **Settings → Billing and taxes**:

- **Sistema Tessera Sanitaria** — your Sistema TS access (username =
  your codice fiscale as registered on sistemats.it, password, pincode),
  the encryption certificate (the one shipped with the module is used
  until you upload a new one), the sender identity (owner's codice
  fiscale; region/ASL/structure codes for structures only), the year
  overview with the **31 January** deadline and the counts, and the
  expense type (`tipoSpesa`) per treatment in your catalog.
- **Sistema TS submissions** — every document sent, with its state,
  protocollo and messages; retry after a rejection; send now.

On the patient page, the **Sistema TS opposition** card records the
patient's objection: documents are still sent, but without the codice
fiscale, and accepted documents are re-sent anonymised. On the invoice
page a panel lists what was sent for that invoice.

## Before you start

- Register on sistemats.it as an *erogatore* to obtain the credentials.
- The clinic's tax id in Settings → General must be its partita IVA.
- Patients need their codice fiscale in the patient record (national id).
- Choose the expense type for treatments that are not plain healthcare
  services (e.g. `IC` for cosmetic work, which is not deductible).
- Test first: the **Test** environment talks to the Sistema TS test
  service; switch to **Production** when the answers are accepted.

## States

| State | Meaning | What to do |
|---|---|---|
| To send | queued for the next run | nothing |
| Accepted / Accepted with warnings | the Sistema TS returned a protocollo | nothing; warnings are shown |
| Rejected | blocking error (e.g. an invalid codice fiscale) | fix the data, then **Retry** |
| Failed | the service could not be reached after eight attempts | check the credentials, then **Retry** |
