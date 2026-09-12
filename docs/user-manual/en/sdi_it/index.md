---
module: sdi_it
last_verified_commit: 0000000
---

# Electronic invoicing for Italy (SDI)

This optional module turns the clinic's **business invoices** into
FatturaPA files and hands them to the Sistema di Interscambio (SDI) of the
Agenzia delle Entrate, then follows the receipts the SDI sends back.

It only concerns invoices whose recipient is a company, an insurer, a fund
or a professional with a *partita IVA*. **Invoices to patients are never
sent to the SDI**: Italian law forbids electronic invoicing for healthcare
services to private persons (art. 10-bis DL 119/2018). Those invoices are
issued as PDF from Billing as usual, and their data belong to the Sistema
Tessera Sanitaria module.

## Screens

Both pages live under **Settings → Billing and taxes**:

- **Electronic invoicing (SDI)** — tax regime, exemption reference, virtual
  stamp duty, and the transport to the SDI (manual or PEC), with a mailbox
  test.
- **SDI files** — every file generated, its state, the receipt, and the
  actions: download the XML, mark it as uploaded, import a receipt, regenerate
  after a rejection, send now (PEC).

The invoice page shows an **SDI panel** with the same information and
actions for that invoice, and an `SDI` chip in the invoice list.

## Before you start

- The clinic's tax id in **Settings → General** must be its partita IVA
  (11 digits); the legal name and address fill the seller block of the file.
- Business recipients need their partita IVA in the invoice's billing data.
  Their SDI recipient code (7 characters) or PEC can be stored in the billing
  address as `sdi_code` / `pec`; otherwise the SDI leaves the invoice in the
  recipient's reserved area on the Agenzia delle Entrate portal.
- Choose the transport:
  - **Manual**: download each XML, upload it in *Fatture e Corrispettivi* or
    send it from your own PEC client, then import the receipt file the SDI
    returns.
  - **PEC**: enter the practice's PEC mailbox (SMTP and IMAP); the system
    sends the files and reads the receipts every two minutes.

## The receipts

| Receipt | State shown | What to do |
|---|---|---|
| RC — ricevuta di consegna | Delivered | nothing |
| MC — impossibilità di recapito | Not deliverable | the invoice is valid; tell the recipient it is in their reserved area |
| NS — notifica di scarto | Rejected | correct the invoice data, then **Regenerate and resend**: the new file keeps the same number and date |

Files and receipts are kept for ten years; records that reached the SDI
block uninstalling the module.
