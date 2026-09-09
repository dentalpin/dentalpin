# 0026 — Italy: Sistema Tessera Sanitaria expense submission for the `sistema_ts` module

- **Status:** accepted
- **Date:** 2026-09-07
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** modules, billing, compliance, italy, privacy

## Context

Issue #134 asks for a sourced spec (sistemats.it and Agenzia delle
Entrate only) before code: what is submitted, how, when, by whom, how
a patient's opposition works, and what has to be kept. The primary
sources read are the Sistema TS technical specification for the
synchronous web service ("Invio dei dati di spesa sanitaria di cui
art. 3 comma 3 D.Lgs. 175/2014 — WEB SERVICE SINCRONO", vers. 1.3,
20/12/2020, 25 pages), the "Strumenti per lo sviluppo" page listing
the asynchronous spec (same date) and the development kit
(ver. 20240214), and the portal's Normativa, 730-spese-sanitarie and
cittadini pages. Points not confirmed from those sources are marked
**open**.

This is the feature that matters to an Italian dental practice: the
patient invoices that ADR 0025 keeps *out* of the SDI go *here*, and
the two are exclusive by law (art. 10-bis DL 119/2018).

### 1. Who is obliged, and for which documents

- Legal basis: art. 3 c. 3 D.Lgs. 175/2014; DM 31 luglio 2015
  (technical modalities), DM 19 ottobre 2020 (expenses from 1 Jan
  2020, payment traceability), DM 29 ottobre 2025 (annual deadline,
  see §4). The portal lists among the obliged subjects "medici e
  odontoiatri", strutture sanitarie accreditate and non accreditate,
  and the other health professions added by later decrees. A dental
  practice is in scope whether it invoices as a professional
  (`Proprietario` = the dentist's codice fiscale) or as a structure
  (`codiceSSA` structure code, "non previsto per il professionista").
- What: every *documento fiscale* (fattura `tipoDocumento=F`, or
  documento commerciale `D`) issued to a **natural person** for
  healthcare expenses, plus its refunds and corrections. Invoices to
  companies/insurers are not Sistema TS documents (they are the SDI
  ones of ADR 0025).

### 2. What is submitted (spec tables 1–6)

Per document:

| Element | Content | Notes |
|---|---|---|
| `Proprietario` | `codiceRegione`, `codiceAsl`, `codiceSSA` (structures only), `cfProprietario` | `cfProprietario` is sent **encrypted** |
| `idDocumentoFiscale` | `pIva` of the issuer, `dataEmissione`, `numDocumentoFiscale{dispositivo, numDocumento}` | `dispositivo` = progressive number of the issuing device/series; DentalPin maps one series → one `dispositivo` |
| `dataPagamento` | payment date ≥ `dataEmissione` unless `flagPagamentoAnticipato=1` (never before 01/01/2015) | the module submits on payment, not on issue |
| `cfCittadino` | patient's codice fiscale, encrypted | **must be absent when `flagOpposizione=1`** |
| `voceSpesa[]` | `tipoSpesa`, `flagTipoSpesa`, `importo` (always positive, also for refunds, 5+2 decimals), `aliquotaIVA` **or** `naturaIVA` (N1–N7 and sub-codes for `F`) | one line per IVA treatment is enough; the tracciato is per expense type, not per catalog item |
| `pagamentoTracciato` | `SI` (traceable per art. 1 c. 679 L. 160/2019) / `NO` (cash) | deductibility depends on it from 2020 |
| `tipoDocumento` | `F` fattura / `D` documento commerciale | dental practices issue `F` |
| `flagOpposizione` | `0` no / `1` the citizen opposes | see §5 |

`tipoSpesa` codes: `TK` ticket, `FC` farmaco/dispositivo CE, `FV`
farmaco veterinario, `AD` acquisto o affitto di dispositivo medico
CE, `AS` farmacia dei servizi, `SR` prestazioni sanitarie (visite,
prestazioni specialistiche e chirurgiche non estetiche, certificazioni,
ricoveri), `CT` cure termali, `PI` protesica e integrativa, `IC`
chirurgia/medicina estetica, `SP` prestazioni sanitarie (professional
row), `SV` spese veterinarie, `AA` altre spese. `flagTipoSpesa` is
`1` with `TK` (pronto soccorso) and `2` with `SR` (intramoenia).
**Open:** the spec's table of admissible codes per subject type is a
graphic in the PDF; the module ships `SR` as the default for
therapeutic dentistry, `IC` for cosmetic items, `AD` for devices sold,
`AA` for the rest, and makes the code a per-catalog-item attribute so
a practice can follow the AdE FAQ for edge cases.

Operations (spec §3.2–3.9): **inserimento** (new document),
**variazione** (replace a sent document, keyed by
`idDocumentoFiscale`), **cancellazione** (withdraw), **rimborso**
(refund of a sent document: same key, positive `importo` of the
refunded amount). A credit note in `billing` therefore maps to
`rimborso`, an edit of an already-sent invoice to `variazione`, a
voided invoice to `cancellazione`.

### 3. How it is submitted

Three ways (spec §1): (1) a file with many documents attached to a
SOAP message — the **asynchronous** web service, outcome deferred
(zip ≤5 MB, MTOM); (2) one document per request — the **synchronous**
web service; (3) the web page on sistemats.it for the provider. The
sync service returns immediately `esitoChiamata` (`0` accepted, `1`
blocking error, `2` accepted with warnings), a 17-digit
`protocollo` when accepted, and `listaMessaggi` (`codice`,
`descrizione`, `tipo` `E`/`W`/`S`).

Authentication (spec §4.1): HTTPS with **basic authentication using
the Sistema TS credentials** (or a CNS certificate); regions and
"enti" use a client certificate (§4.2, different endpoint path). The
request also carries `pincode` (the provider's Sistema TS PIN,
encrypted with the Sistema TS public certificate shipped in the kit;
in clear only for Entratel intermediaries) and the encrypted codici
fiscali. Endpoints: test
`https://invioSS730pTest.sanita.finanze.it/DocumentoSpesa730pWeb/DocumentoSpesa730pPort`,
production `https://invioSS730p.sanita.finanze.it/DocumentoSpesa730pWeb/DocumentoSpesa730pPort`.
A self-hosted practice can therefore submit directly with its own
credentials (username = codice fiscale, password, pincode, obtained by
registering on sistemats.it as an erogatore); no intermediary is
required. The encryption certificate is periodically regenerated
(kit note "Rigenerazione certificato di cifratura", 14/02/2024), so
it must be a replaceable setting, not a constant.

### 4. When

- DM 29 ottobre 2025 (implementing art. 12 D.Lgs. 1/2024 as replaced
  by art. 5 D.Lgs. 81/2025): expense data are sent **annually, by 31
  January of the year following the expense**, starting with 2025
  expenses (31 Jan 2026 fell on a Saturday, the portal moved it to
  2 Feb 2026). Before that decree the cadence was semi-annual/monthly.
- The portal publishes a yearly "Calendario invio spese sanitarie"
  note (2026 note dated 07/01/2026; it is an image PDF and was not
  machine-read — **open**: confirm each year's dates from it).
- Corrections after the deadline go through `variazione` /
  `cancellazione`; AdE then opens the citizens' opposition window
  (§5) and builds the precompilata.
- Sanctions: art. 3 c. 5-bis D.Lgs. 175/2014 — €100 per document,
  max €50,000 per year; no sanction if the data are sent within five
  days after the deadline, one third if corrected within five days of
  AdE's notice.

The module submits **continuously** (on payment, through the sync
service, with a retry queue) rather than as a January batch: nothing
in the rules requires batching, and continuous submission means a
practice is never one crashed batch away from a sanction. A "pending
for year N" view and a "send everything unsent for year N" action
cover the batch mindset.

### 5. Opposition

Two mechanisms, both from the portal and the spec:

1. **At the time of the expense**, the patient tells the provider.
   The provider still transmits the document, with
   `flagOpposizione=1` and **without** `cfCittadino` (spec table 5:
   "Deve essere assente se flagOpposizione = 1"). The data then serve
   only aggregate statistics.
2. **Afterwards via the portal**, in the annual window that follows
   the providers' deadline (portal: "09 febbraio – 8 marzo"; for
   2025 expenses 10 February – 8 March 2026), with SPID, CIE or
   TS-CNS, per document. This one needs nothing from the software.

The module therefore keeps a per-patient opposition record in its own
table (`sistema_ts_patient_opposition`: patient id, opposed since,
revoked at, who recorded it), shows it in the patient record, and
applies it at submission time: any document for an opposed patient is
sent anonymised (flag 1, no CF). Opposition is never a reason to skip
the document, and an existing sent document is re-sent as
`variazione` when the flag changes (**open**: whether AdE expects a
variazione or a cancellazione + new inserimento for a late
opposition; the sync spec allows both, the portal is silent).

### 6. What to keep

Per submitted document the module stores the exact request payload,
`esitoChiamata`, `protocollo`, `listaMessaggi`, timestamp and
environment. The `protocollo` is the only proof of a submission. No
Sistema TS source states a retention period for it; the module keeps
it as long as the fiscal document it belongs to (10 years, art. 2220
c.c.; ADR 0025 §5), which also covers the sanction terms of art. 3
c. 5-bis. Codici fiscali are health-related personal data (GDPR
art. 9): the stored payload keeps them encrypted exactly as sent.

## Decision

1. `sistema_ts` is a country-gated (`IT`) module beside `billing`
   in the `verifactu` shape (own `sistema_ts_*` tables, own Alembic
   branch, own Nuxt layer, hook through `BillingHookRegistry`,
   uninstall round-trip test). It handles invoices and credit notes
   whose recipient is a natural person; B2B invoices are ADR 0025's.
2. Transport: the **synchronous web service** with basic auth and the
   practice's own Sistema TS credentials (username, password, pincode,
   the Sistema TS encryption certificate as an updatable setting),
   test and production environments switchable like verifactu's.
   The asynchronous zip service is a later optimisation for backfills.
3. Submission is continuous on payment with a retry queue; `billing`
   credit notes map to `rimborso`, edits to `variazione`, voids to
   `cancellazione`. `tipoSpesa` is a per-catalog-item attribute
   defaulting to `SR`; `pagamentoTracciato` derives from the payment
   method recorded by `payments`.
4. Opposition lives in `sistema_ts_patient_opposition`, is visible in
   the patient record, and turns every submission for that patient
   into `flagOpposizione=1` without `cfCittadino`.
5. Every request/response pair is stored immutably with its
   `protocollo` for 10 years; the settings screen shows the annual
   deadline and the count of unsent documents for the current year.

## Consequences

### Good

- Direct submission with credentials the practice already holds;
  nothing to accredit, no vendor in the middle.
- The one-document-per-call service maps 1:1 onto the verifactu
  queue/worker shape, including immediate error surfacing.
- Opposition is honoured mechanically and auditable.

### Bad / accepted trade-offs

- Per-call submission is chattier than a yearly zip; acceptable at
  dental volumes.
- The `tipoSpesa` per-subject table and the late-opposition operation
  are marked open and need confirming against AdE FAQ during
  implementation.
- The Sistema TS certificate rotation is one more thing a self-hosted
  admin must update when the portal announces it.

## Alternatives considered

- **A flag on the invoice inside `billing`.** — Different
  destination, cadence and data; rejected by the issue and by the
  module rules.
- **Asynchronous batch only.** — Deferred outcomes and a 5 MB zip
  pipeline for a practice that issues a few documents a day; sync is
  simpler and gives the `protocollo` immediately.
- **Skip opposed patients' documents.** — The spec requires the
  document without CF; skipping would under-report.
- **Opposition as a column on `patients`.** — Module data in a core
  table; rejected by the module rules.

## How to verify the rule still holds

- Backend test: a paid patient invoice in an `IT` clinic with the
  module enabled produces exactly one `inserimento` payload that
  validates against the kit's XSD; an opposed patient's payload has
  `flagOpposizione=1` and no `cfCittadino`.
- Backend test: a credit note produces a `rimborso` with positive
  `importo`; an invoice to a company produces no `sistema_ts` row.
- Backend test: `esitoChiamata=1` keeps the row `rejected` with the
  `E` messages; `0`/`2` store the 17-digit `protocollo`.
- Round-trip uninstall test leaves no `sistema_ts_*` table or column.

## References

- Issue #134; ADR 0025 (SDI); `docs/modules/verifactu.md`;
  `backend/app/modules/billing/hooks.py`
- Sistema TS, "Strumenti per lo sviluppo" (specs, kit 20240214):
  <https://sistemats1.sanita.finanze.it/portale/it/spese-sanitarie/documenti-e-specifiche-tecniche-strumenti-per-lo-sviluppo>
- Sistema TS, WS sincrono spec v1.3 (20/12/2020) — tables 1–6, §3, §4
- Sistema TS, Normativa (D.Lgs. 175/2014 art. 3, DM 31/07/2015, DM
  19/10/2020, DM 29/10/2025, provvedimenti opposizione):
  <https://sistemats1.sanita.finanze.it/portale/it/web/guest/spese-sanitarie-normativa>
- Sistema TS, 730 spese sanitarie (obliged subjects, opposition in
  February): <https://sistemats1.sanita.finanze.it/portale/it/730-spese-sanitarie>
- Sistema TS, cittadini (opposition window and credentials):
  <https://sistemats1.sanita.finanze.it/portale/it/web/guest/spese-sanitarie-cittadini>
- Sistema TS, Anno 2026 (calendar note 07/01/2026):
  <https://sistemats1.sanita.finanze.it/portale/it/anno-2026>
- Art. 10-bis DL 119/2018; art. 1 c. 679 L. 160/2019; art. 3 c. 5-bis
  D.Lgs. 175/2014; art. 5 D.Lgs. 81/2025
