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
| United States | ✅ `en` | ✅ | ✅ patient invoicing works as-is | ❌ CDT coding, X12 837D claims; HIPAA gap analysis | #137 |
| Mexico | ✅ `es` | ✅ | ❌ CFDI stamping through a PAC | n/a | #138 |
| Brazil | ✅ `pt` | ✅ | ❌ NFS-e | ❌ TISS | #139 |
| Germany | ✅ `de` | ❌ | ❌ BEMA / GOZ, KZV submission | ❓ Telematikinfrastruktur feasibility | #135, #136 |
| Italy | ✅ `it` | ❌ | ❌ FatturaPA / SDI for B2B/B2G invoices only — patient invoices may not go through the SDI (art. 10-bis DL 119/2018; ADR 0025, spec accepted, module pending) | ❌ Sistema Tessera Sanitaria (ADR 0026, spec accepted, module pending) | #133, #134 |
| Poland | ✅ `pl` | ❌ | ❌ KSeF | ❌ P1 / EDM | #143 |
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
