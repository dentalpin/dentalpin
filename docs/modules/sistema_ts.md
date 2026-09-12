# sistema_ts — Sistema Tessera Sanitaria (Italy)

**Status:** phase 2 (backend, worker, API, Nuxt layer). Issue #134, ADR 0026.

## What it does

For an `IT` clinic, every **paid invoice to a patient** (a natural person:
no partita IVA in the billing data) is sent to the Sistema Tessera
Sanitaria synchronous web service as an `inserimento`, so the expense
appears in the patient's pre-filled tax return. Credit notes go as
`rimborso`, voided invoices as `cancellazione`, and a change of the
patient's opposition as `variazione`. B2B invoices are the SDI module's
(ADR 0025); the two are exclusive by art. 10-bis DL 119/2018.

A worker runs every two minutes: it scans billing for new paid patient
invoices (idempotent, one `inserimento` per invoice, from `sync_from` if
set), then sends due documents one by one with basic auth and the
RSA-encrypted pincode (vendored `certs/SanitelCF.cer`, replaceable per
clinic). The response's `esitoChiamata` decides the state: `accepted`
(0), `accepted_with_warnings` (2) or `rejected` (1, with the blocking
messages); transport errors back off up to eight attempts, a credential
failure pauses the clinic ten minutes.

## Document contents

| Element | Source |
|---|---|
| `pIva`, `dataEmissione`, `numDocumentoFiscale{dispositivo, numDocumento}` | clinic tax id, invoice issue date, settings `dispositivo` (default `1`), invoice number |
| `dataPagamento`, `flagPagamentoAnticipato` | latest payment date of the invoice's payments |
| `cfCittadino` (encrypted) | `patients.national_id` as codice fiscale — absent when the patient opposes |
| `voceSpesa[]` | invoice lines grouped by `tipoSpesa` (per catalog item, default `SR`) and IVA: `aliquotaIVA` for taxable lines, `naturaIVA=N4` for exempt |
| `pagamentoTracciato` | `NO` if any payment was cash, else `SI` |
| `tipoDocumento` | `F` |
| `flagOpposizione` | from `sistema_ts_patient_opposition` |

## Opposition

`PUT /opposition/{patient_id}` records (or revokes) the patient's
opposition; documents are still sent, anonymised, and accepted documents
of the patient are re-sent as `variazione`. The patient record shows the
flag (phase 2 UI).

## Screens

Settings → Billing and taxes → **Sistema Tessera Sanitaria** (access
credentials with write-only password/pincode, certificate upload, sender
identity, year overview: deadline, not-yet-sent / accepted / rejected
counts, and the expense type per catalog item) and **Sistema TS
submissions** (per year, states, protocollo, retry, send now). The
patient summary gets an **opposition card** (record / revoke, with a
note); the invoice page a panel listing the invoice's submissions.
User manual: `docs/user-manual/{en,es}/sistema_ts/index.md`.

## Endpoints

`GET/PUT /settings` (credentials, identity, year overview with the
31 January deadline), `GET /documents`, `GET /documents/by-invoice/{id}`,
`POST /documents/{id}/retry`, `POST /queue/process-now`,
`GET/PUT /opposition/{patient_id}`, `GET /item-types`,
`PUT /item-types/{catalog_item_id}`.

## Not yet

The asynchronous zip service, receipt PDFs (`Ricevute730`), the AdE
notification services.
