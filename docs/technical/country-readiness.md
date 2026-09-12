# Country readiness — what each market still needs

> One place to see what each market needs before a practice there can
> run DentalPin as its only system, and which of those pieces is open
> for someone to pick up (issue #146). Every row links to the issue
> with the detail. Update this file whenever a country piece lands —
> the issue that created it went stale within a quarter, which is
> exactly the failure mode a repo-tracked doc avoids.

**The honest summary:** DentalPin is complete for **Spain** and
**India (GST invoicing)**, and usable anywhere a practice invoices
outside its practice software. Everywhere else one or two country
pieces are missing — and they are the pieces a local developer can
write far better than we can.

## What "ready" means

Three independent axes per market:

1. **UI language** — the staff-facing interface. Nine languages ship
   today (en, es, fr, pt, ta, de, hu, pl, it), core **and** every
   module layer, with CI-enforced key parity.
2. **Invoicing / tax compliance** — whatever the tax authority
   requires of invoices (certification, real-time reporting, document
   formats). This is per-country by nature and is DentalPin's
   established plug-in seam: `verifactu` (Spain) and `india_gst`
   (India) are the two reference implementations.
3. **Clinical / insurance interop** — statutory billing or clinical
   networks (KZV, SESAM-Vitale, TISS…). Only relevant in some
   markets, and often gated on a feasibility question about
   open-source software being admitted at all.

Patient-facing **communications** (email templates, PDFs) render in
five languages (es, en, fr, pt, ta) — a market whose language is
UI-only still sends patient documents in one of these until its
templates are contributed.

## Where each market stands

| Market | UI | Comms | Invoicing / tax | Clinical / insurance interop | Open issues |
|---|---|---|---|---|---|
| Spain | ✅ `es` | ✅ | ✅ `verifactu` module (AEAT) | n/a | — |
| India | ✅ `en` + `ta` | ✅ | ✅ `india_gst` module (CGST/SGST/IGST, GSTIN checksum, FY numbering; e-invoice is applicability-tracking only) | ❓ ABDM voluntary? DPDP audit | #145 (e-invoicing GSP/IRP, DPDP, ABDM) |
| France | ✅ `fr` | ✅ | ❌ e-invoicing reform (partner platforms, e-reporting); invoicing outside the Assurance Maladie flow until the FSE connector exists | ❌ `fr_ccam` (CCAM dentaire, tariffs, 100 % Santé baskets, devis conventionnel) then `fr_fse` connector to a homologated engine sold as API (ADR 0028); no in-house homologation; self-hosted installations are outside HDS, hosted offers need an HDS host | #411 (fr_ccam), #141 (answered), #142 |
| Portugal | ✅ `pt` | ✅ | ❌ AT certification is not possible for a self-hosted, modifiable program (producer-exclusive signing key, Portaria 363/2010 art. 3; ADR 0027) — `pt_invoicing` connector to a certified invoicing API (InvoiceXpress, Moloni, Vendus…) pending; until then invoice with a certified program | n/a | #140 (answered) |
| United States | ✅ `en` | ✅ | ✅ patient invoicing works as-is | ❌ Claims: no US regulator certifies dental PMS — the blocker is IP, not approval. DentalPin ships no CDT (ADA commercial licence; the practice supplies its own) and writes no X12 837D (X12's licence forbids Open Source licensing of the combined software, and ADR 0004 converts to Apache 2.0); `us_claims` sends a non-standard payload to a clearinghouse acting as the practice's business associate (45 CFR 162.930(b); ADR 0035). HIPAA: self-hosted means DentalPin is no business associate and signs no BAA; the hosted offer is one and does. Read-access logging, automatic logoff and emergency access are open before any readiness claim | #137 |
| Mexico | ✅ `es` | ✅ | ❌ CFDI stamping through a PAC | n/a | #138 |
| Brazil | ✅ `pt` (pt-BR wording tracked separately) | ✅ | ❌ NFS-e: feasible, no software certification exists — the practice emits from its own software with an ICP-Brasil e-CNPJ (Res. CGNFS-e 3/2023 art. 3º § único); `br_nfse` pending, targeting the SEFIN Nacional API with the `IBSCBS` groups (ADR 0034) | ❌ TISS: feasible — "qualquer solução tecnológica poderá ser utilizada" (RN 501/2022, CO item 139); `br_tiss` pending, one protocol and N per-operadora connections, Comunicação 04.03.00; DentalPin never talks to ANS (ADR 0034) | #139 (answered) |
| Germany | ✅ `de` | ❌ | ❌ GOZ private invoicing: `de_goz` module pending (no approval needed); statutory BEMA/KZV billing not possible for a self-hosted, modifiable program — the KZBV Eignungsfeststellung is per system and version and the submission files come from KZBV modules (Anlage 1 BMV-Z; ADR 0031) — bill the KZV with a KZBV-listed PVS | ❌ TI: DentalPin talks to the practice's gematik-approved Konnektor/TI-Gateway, never is one; `de_ti` (VSDM first, KIM transport second) pending; EBZ/E-Rezept/ePA stay with the approved PVS (ADR 0032) | #135, #136 (answered) |
| Italy | ✅ `it` | ❌ | ❌ FatturaPA / SDI for B2B/B2G invoices only — patient invoices may not go through the SDI (art. 10-bis DL 119/2018; ADR 0025, spec accepted, module pending) | ❌ Sistema Tessera Sanitaria (ADR 0026, spec accepted, module pending) | #133, #134 |
| Poland | ✅ `pl` | ❌ | ❌ KSeF: mandatory 2026-02-01 / 2026-04-01, penalties 2027-01-01 — but art. 106ga ust. 2 pkt 4 exempts invoices to natural persons, so almost every patient invoice is out of scope and KSeF matters only for B2B; `pl_ksef` pending, **no certification needed** (MF publishes the OpenAPI contract, SDKs and three environments); patient sales stay on the practice's own kasa fiskalna online (ADR 0033) | ❌ P1/EDM: **feasible for a self-hosted open-source system** — CeZ issues the TLS/WSS certificates to the practice through RPWDL 2.0, the integration documentation is public, the Projectathon is voluntary; `pl_p1` pending (zdarzenia medyczne + EDM index, then EDM production, then e-recepta/e-skierowanie); the dentist's qualified signature never leaves the dentist; NFZ settlement out of scope (ADR 0033) | #143, #144 |
| Hungary | ✅ `hu` | ❌ | ✅ `nav_online` module (NAV Online Számla 3.0 real-time reporting, phase 1: CREATE/STORNO) | n/a | #341 |
| Tamil-speaking markets | ✅ `ta` | ✅ | see India | see India | — |

Legend: ✅ done · ❌ missing, scoped in the linked issue · ❓ open
feasibility question — a sourced "no, and here is the rule" is as
valuable as an implementation.

## Three things worth knowing before you pick one up

1. **Several of these are research issues, not coding issues.** #136
   (Telematikinfrastruktur), #140 (AT certification), #141
   (SESAM-Vitale) and #145's ABDM half all start with: can an
   open-source product a practice installs and can modify be
   certified, homologated or admitted at all in that market?
2. **The invoicing seam is proven twice.** Both `verifactu` and
   `india_gst` are optional, country-gated modules that plug into
   billing through the `BillingComplianceHook` — snapshotting
   compliance data at issue time, own Alembic branch, own settings
   page. Read `docs/modules/india_gst.md` and the verifactu module
   docs before starting a third; the pattern transfers almost
   mechanically (#133 explicitly asks for "the verifactu pattern
   applied to IT").
3. **UI language is never the blocker anymore.** Since the 2026-08
   i18n wave, all nine languages cover core + every module layer, and
   adding a tenth is a translation-only contribution. The remaining
   language gap is **communications** (templates/PDFs for de, hu, pl,
   it) — smaller than a UI sweep and a good first contribution for a
   native speaker.
