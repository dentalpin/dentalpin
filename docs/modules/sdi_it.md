# sdi_it — FatturaPA / SDI e-invoicing (Italy)

**Status:** phase 1 (manual transport). Issue #133, ADR 0025.

## What it does

When an `IT` clinic issues an invoice or a credit note **to a soggetto
passivo IVA** (the recipient's tax id is a valid partita IVA), the module
renders the FatturaPA `FPR12` file (schema v1.2, Specifiche tecniche
v1.9) and stores it as an `sdi_it_records` row in state `pending`. The
admin downloads the XML, hands it to the SDI (portal upload or the
clinic's PEC), marks the record `exported`, and imports the receipt the
SDI returns:

| Receipt | State | What to do |
|---|---|---|
| `RC` ricevuta di consegna | `delivered` | nothing |
| `MC` impossibilità di recapito | `undeliverable` | tell the recipient the invoice is in their area riservata |
| `NS` notifica di scarto | `rejected` | fix the data and resend within 5 days: editing the recipient on the invoice (billing's *edit billing party*, allowed only while the latest record is `rejected`) queues a new file automatically; after fixing clinic data use **Requeue**. Same number and date, new progressivo |

Invoices to natural persons never produce a record: healthcare invoices to
persone fisiche may not be electronic (art. 10-bis DL 119/2018). They are
issued as PDF/paper by `billing` and belong to the Sistema Tessera
Sanitaria module (ADR 0026). The hook records
`compliance_data["IT"] = {"sdi": "not_applicable", "reason": "b2c_healthcare_art_10bis"}`
on those invoices so the UI can say why.

## Configuration (`/api/v1/sdi_it/settings`)

- `enabled`, `transport` (`manual`), `regime_fiscale` (`RF01` ordinario,
  `RF19` forfettario…), `bollo_virtuale` (add the €2 virtual stamp when
  the exempt total exceeds €77.47), `riferimento_normativo` (text printed
  in the exempt riepilogo; default "Esente IVA art. 10 n. 18 DPR 633/72").
- The clinic's `tax_id` must be its partita IVA; `legal_name` and the
  address (street, postal code, city, province) fill `CedentePrestatore`.
- Recipient routing: `billing_address.sdi_code` (7-char codice
  destinatario) or `billing_address.pec`; otherwise `0000000` and the SDI
  parks the invoice in the recipient's area riservata.

## Data

- `sdi_it_settings` — one row per clinic (+ the `ProgressivoInvio` counter).
- `sdi_it_records` — one row per file: XML, file name, state, receipt
  XML, `IdentificativoSdI`, errors. Records that reached the SDI block
  uninstall (they are the proof of issuance; keep 10 years, ADR 0025 §5).

## Endpoints

`GET/PUT /settings`, `GET /records`, `GET /records/{id}/xml`,
`POST /records/{id}/exported`, `POST /records/{id}/requeue`,
`POST /receipts` (`{xml, file_name?}`).

## Not in phase 1

PEC transport (SMTP/IMAP automation), SdICoop, digital signature,
`Allegati` (PDF copy inside the XML), the Nuxt layer.
