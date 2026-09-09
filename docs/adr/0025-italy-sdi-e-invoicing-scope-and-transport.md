# 0025 — Italy: FatturaPA/SDI e-invoicing scope and transport for the `sdi_it` module

- **Status:** accepted
- **Date:** 2026-09-07
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** modules, billing, compliance, italy

## Context

Issue #133 asks for a sourced spec before any code: which FatturaPA
version, which fields a dental practice fills, how exempt healthcare
maps to *natura* codes, how a self-hosted installation transmits,
which receipts come back, what has to be stored and for how long, and
whether SDI constrains numbering. Everything below comes from Agenzia
delle Entrate (AdE) publications or the primary legislation on
normattiva.it; the file paths point at the official documents that
were read. Where a point could not be confirmed from an official
source it is marked **open**.

The single fact that shapes the module is not in the FatturaPA spec
but in the law: **an Italian dental practice is forbidden from sending
its patient invoices through the SDI.**

### 1. The B2C healthcare prohibition (art. 10-bis DL 119/2018)

Art. 10-bis of decreto-legge 23 ottobre 2018 n. 119 (as in force today
on normattiva.it) says that the subjects required to send data to the
Sistema Tessera Sanitaria "non possono emettere fatture elettroniche
ai sensi delle disposizioni di cui all'articolo 1, comma 3, del
decreto legislativo 5 agosto 2015, n. 127, con riferimento alle
fatture i cui dati sono da inviare al Sistema tessera sanitaria".
Art. 9-bis comma 2 of DL 14 dicembre 2018 n. 135 extends the same rule
to subjects *not* obliged to feed the Sistema TS, "con riferimento
alle fatture relative alle prestazioni sanitarie effettuate nei
confronti delle persone fisiche". The rule was originally limited to
tax year 2019 and was extended one year at a time; the vigente text on
normattiva.it no longer carries a year limit (the last extension chain
ended with decreto legislativo 12 giugno 2025 n. 81, which made it
permanent — the normattiva page consulted shows the text "vigente"
with no expiry).

Consequences for a dental practice (an *odontoiatra* is an obliged
Sistema TS sender, see ADR 0026):

- An invoice for dental treatment issued to a natural person is issued
  in analogue form (paper or PDF) and its data go to the Sistema TS
  (ADR 0026 / issue #134). It never goes to the SDI, whether or not
  the patient would like it to.
- Invoices to *soggetti passivi IVA* (insurers, funds, companies,
  other professionals, a PA) are ordinary electronic invoices under
  art. 1 c. 3 D.Lgs. 127/2015 and **must** go through the SDI. The
  same holds when the practice is in the regime forfettario (mandatory
  for all forfettari since 1 January 2024, art. 18 DL 36/2022).
- **Open:** how a service rendered to a patient but invoiced to an
  insurer is described. AdE's FAQ on e-invoicing say the invoice to the
  third party must not carry the patient's identifying data; the exact
  FAQ number should be quoted in the module docs when the XML builder
  is written. The builder must never copy patient name or codice
  fiscale into `Descrizione`.

So the `sdi_it` module is a **B2B/B2G e-invoicing module**, not the
way patient invoices are issued. That is the opposite of what the
XDENT comparison implied, and the docs/marketing sentence should say
so.

### 2. Format: FatturaPA v1.9, schema VFPR12 1.2.3

- The current AdE "Specifiche tecniche" are **version 1.9**, in force
  since 1 April 2025 (allegato A to provvedimento AdE, downloaded as
  `Specifiche_tecniche_v1.9.pdf`, 189 pages). The XML schema for
  private recipients is `Schema_VFPR12` **v1.2.3**, transmission format
  `FPR12` (`FPA12` only for public administrations; those additionally
  require a qualified signature).
- `TipoDocumento` values a practice uses: `TD01` fattura, `TD04` nota
  di credito, `TD05` nota di debito, `TD06` parcella (spec table
  "TipoDocumento"). Self-billing and reverse-charge types (TD16–TD28)
  are out of scope.
- **Natura for exempt healthcare:** dental services are exempt under
  art. 10 comma 1 n. 18 DPR 633/72. The spec's Natura table lists
  `N4 esenti` as the code for exempt operations, with the note that
  for exempt lines "occorre indicare la Natura N4" (spec, blocco
  DatiRiepilogo). Each exempt line therefore carries
  `AliquotaIVA=0.00` + `Natura=N4`, and the riepilogo for N4 carries
  `RiferimentoNormativo` = "Esente IVA art. 10 n. 18 DPR 633/72".
  Non-therapeutic services (purely cosmetic) are taxable at 22%:
  `AliquotaIVA=22.00`, no Natura. The catalog therefore needs a
  per-item "IVA treatment" (exempt N4 / 22%) exactly like verifactu's
  `E1` mapping.
- **Bollo:** exempt invoices above €77.47 owe the €2 stamp duty
  (art. 13 tariffa allegata al DPR 642/1972); on an e-invoice it is
  declared in `DatiBollo` (`BolloVirtuale=SI`, `ImportoBollo=2.00`).
- Fields a dental practice fills (FPR12 header/body, spec chapter
  "Descrizione degli elementi informativi"):
  - `DatiTrasmissione`: `IdTrasmittente` (IT + the practice's own
    codice fiscale or partita IVA), `ProgressivoInvio` (unique per
    transmitter), `FormatoTrasmissione=FPR12`, `CodiceDestinatario`
    (7-char recipient code) or `0000000` + `PECDestinatario`.
  - `CedentePrestatore`: `IdFiscaleIVA`, `CodiceFiscale`, `Anagrafica`,
    `RegimeFiscale` (`RF01` ordinario, `RF19` forfettario), `Sede`,
    optional `IscrizioneREA`, `Contatti`.
  - `CessionarioCommittente`: `IdFiscaleIVA` and/or `CodiceFiscale`,
    `Anagrafica`, `Sede`.
  - `DatiGeneraliDocumento`: `TipoDocumento`, `Divisa=EUR`, `Data`,
    `Numero` (max 20 chars), `DatiBollo`, `ImportoTotaleDocumento`,
    `Causale`; `DatiCassaPrevidenziale` only if the practice charges a
    contribution line.
  - `DettaglioLinee`: `NumeroLinea`, `Descrizione`, `Quantita`,
    `PrezzoUnitario`, `PrezzoTotale`, `AliquotaIVA`, `Natura`.
  - `DatiRiepilogo` per (aliquota, natura): `ImponibileImporto`,
    `Imposta`, `EsigibilitaIVA`, `RiferimentoNormativo`.
  - `DatiPagamento`: `CondizioniPagamento` (`TP02` completo, `TP01`
    rate), `DettaglioPagamento` (`ModalitaPagamento` MP01 contanti,
    MP05 bonifico, MP08 carta…, `ImportoPagamento`,
    `DataScadenzaPagamento`).
  - `Allegati`: the branded PDF, base64 (optional).
- Signature: the spec (§1.2.1) states the SDI "gestisce sia fatture
  elettroniche prive di firma elettronica che fatture elettroniche
  alle quali sia apposta firma elettronica". For FPR12 the signature is
  optional; the module ships unsigned XML (file name
  `IT<IdCodice>_<progressivo 5 alnum>.xml`, spec §1.2.2).

### 3. Transmission channels and what "self-hosted" means

The spec (§1.3 and the "Sistema di Accreditamento" pages) lists four
channels from the sender's side:

| Channel | Requirements | Fit for a self-hosted practice |
|---|---|---|
| **PEC** (first message to `sdi01@pec.fatturapa.it`, then the address the SDI answers with; ≤30 MB) | a PEC mailbox — every Italian professional iscritto all'albo already has one by law | yes: SMTP send + IMAP poll of receipts, no accreditation |
| **Web upload** in "Fatture e Corrispettivi" (≤5 MB) | SPID/CIE/CNS login, manual | fallback: export XML, import receipt |
| **SdICoop** (SOAP web service, mutual TLS) | accreditation of the endpoint through the Sistema di Accreditamento (interoperability test, certificate issued by SdI), fixed URL | only for a hosted operator that accredits once for all tenants |
| **SdIFtp** | as SdICoop, high volume | no |

Nothing in the rules requires an intermediary; the practice can be
its own `IdTrasmittente`. An intermediary only changes who signs the
transmission, not the format.

### 4. Receipts and states (spec §1.5.7 and file-name table "Tipo di messaggio")

For an FPR12 invoice the SDI returns exactly one of:

| Code | Name | Meaning for the practice |
|---|---|---|
| `NS` | Ricevuta di scarto | rejected by the SDI checks (schema, codes, duplicate); the invoice is considered *not issued*. Fix and resend with the **same number and date** within 5 days (AdE circolare 13/E 2 luglio 2018, §1.6) |
| `RC` | Ricevuta di consegna | delivered to the recipient's channel; terminal, nothing to do |
| `MC` | Ricevuta di impossibilità di recapito | the recipient channel failed (PEC bounced or silent for 40 h, spec §1.3); the invoice is still validly issued and is placed in the recipient's area riservata. The practice must tell the recipient by other means that the invoice is available there |

`MT` (metadata) and the PA-only receipts (`AT`, `DT`, `NE`/`EC`) do
not apply to FPR12. The module state machine is therefore
`draft → queued → sent (awaiting) → delivered (RC) | undeliverable (MC, action: notify recipient) | rejected (NS, action: fix & resend)`.
Only NS and MC need a human; that is the "subsanación" analogue.

### 5. Storage and conservazione

- Electronic invoices are "documenti informatici" and must be kept in
  *conservazione elettronica a norma* (art. 39 c. 3 DPR 633/72; DM 17
  giugno 2014, within three months of the tax-return deadline of the
  year the invoice belongs to).
- Retention: 10 years (art. 2220 codice civile), and in any case until
  the assessment terms of art. 57 DPR 633/72 / art. 43 DPR 600/73 have
  run.
- AdE provides a **free conservation service** for every invoice that
  passed through the SDI once the taxpayer adheres in "Fatture e
  Corrispettivi" (art. 1 c. 6-bis D.Lgs. 127/2015; provvedimento AdE
  30 aprile 2018). Adhering makes the obligation the practice's, met
  through AdE; no software component becomes a *conservatore*.

### 6. Numbering

Art. 21 c. 2 lett. b DPR 633/72 requires a "numero progressivo che
identifichi in modo univoco" the invoice; AdE risoluzione 1/E del 10
gennaio 2013 confirms that any scheme guaranteeing uniqueness and
progression is valid, including yearly restarts and *sezionali*
(series). The SDI enforces uniqueness (a repeated number/date for the
same cedente is a scarto). `billing` already gives per-series
progressive numbers, which is sufficient. Because the B2C patient
invoices are analogue and the B2B ones electronic, a practice should
use two series (e.g. `A` analogue, `E` electronic); this is a
configuration recommendation, not a code constraint.

## Decision

1. `sdi_it` is a country-gated (`IT`) billing compliance module in
   the `verifactu` shape (own tables `sdi_it_*`, own Alembic branch,
   own Nuxt layer, hook through `BillingHookRegistry`). It handles
   **only invoices whose recipient is a soggetto passivo IVA / PA**.
   Invoices to natural persons are never queued; the hook enforces
   this from the recipient's fiscal identity, not from a checkbox.
2. XML: FatturaPA v1.9 / VFPR12 1.2.3, `FPR12`, unsigned, validated
   against the official XSD in tests. Catalog items carry an IVA
   treatment (`N4` exempt art. 10 n. 18 / 22%); exempt invoices over
   €77.47 get `DatiBollo`.
3. Transport is a driver interface with three implementations, in
   this order of delivery: **PEC** (default for self-hosted), **manual**
   (export XML / import receipt XML), **SdICoop** (later, for a hosted
   operator that accredits). No intermediary abstraction.
4. Receipt handling models `RC`, `NS`, `MC` as above; `NS` re-issues
   with the same number and date; `MC` raises a task to notify the
   recipient.
5. The module stores the sent XML, every receipt XML and the SDI file
   identifier immutably for **10 years** and documents that the
   practice must adhere to AdE's free conservation service (or a
   conservatore). It does not claim to be a conservation system.
6. Numbering stays in `billing`; docs recommend a dedicated series for
   electronic invoices.

## Consequences

### Good

- The scope is legally right: no risk of shipping a feature that
  pushes patient data through the SDI in breach of art. 10-bis.
- PEC-first means a practice can go live with the credentials it
  already owns and nothing to accredit.
- The verifactu shape is reused unchanged; the only new concept is the
  recipient-type gate.

### Bad / accepted trade-offs

- A practice whose revenue is almost all B2C gets little from this
  module; the feature that matters to them is ADR 0026. The website
  copy must not promise "invoicing through SDI" for patients.
- PEC needs mailbox credentials in the settings screen and IMAP
  polling in the worker; receipts can take up to 40 h (PEC) before
  `MC` is known.
- Two invoice series per practice is a docs recommendation the user
  can ignore.

## Alternatives considered

- **Treat SDI as the way to issue every invoice (as in Spain).** —
  Illegal for B2C healthcare (art. 10-bis DL 119/2018); rejected.
- **SdICoop first.** — Requires per-installation accreditation and a
  fixed public endpoint; unrealistic for self-hosted practices.
- **Require an intermediary/provider.** — Adds a vendor in the middle
  of a self-hosted product for no legal benefit.
- **Store nothing beyond the invoice row.** — The receipt is the only
  proof of issuance; keep it.

## How to verify the rule still holds

- Backend test: an invoice whose recipient has no partita IVA (a
  patient) never creates an `sdi_it_records` row, even with the module
  enabled and the clinic in `IT`.
- Backend test: generated XML validates against
  `Schema_VFPR12_v1.2.3.xsd` (vendored in the module's tests) and an
  exempt line carries `Natura=N4` with `AliquotaIVA=0.00`.
- Backend test: `NS` handling re-queues with the same `Numero`/`Data`;
  `MC` sets state `undeliverable` and creates the notify task.
- Round-trip uninstall test leaves no `sdi_it_*` table or column.

## References

- Issue #133; ADR 0026 (Sistema TS); `docs/modules/verifactu.md`
- `backend/app/modules/billing/hooks.py` (`BillingComplianceHook`,
  `BillingHookRegistry`)
- Art. 10-bis DL 119/2018 (testo vigente):
  <https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2018-10-23;119~art10bis!vig=>
- Art. 9-bis DL 135/2018; art. 1 c. 3 D.Lgs. 127/2015; D.Lgs. 81/2025
- AdE, Specifiche tecniche fattura elettronica v1.9 (allegato A) and
  `Schema_VFPR12` 1.2.3:
  <https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/formato-fatturapa/>
- AdE, Sistema di Accreditamento / canali di trasmissione:
  <https://www.fatturapa.gov.it/it/sistema-interscambio/>
- AdE circolare 13/E del 2 luglio 2018 (scarto, re-issue within 5 days)
- AdE risoluzione 1/E del 10 gennaio 2013 (numbering)
- DPR 633/72 art. 10 n. 18, art. 21, art. 39; DM 17 giugno 2014;
  art. 2220 c.c.; DPR 642/1972 (bollo)
