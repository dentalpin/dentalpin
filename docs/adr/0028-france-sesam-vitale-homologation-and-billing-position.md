# 0028 — France: SESAM-Vitale homologation and the billing position for FR clinics

- **Status:** proposed
- **Date:** 2026-09-07
- **Deciders:** maintainers (@martinezsalmeron)
- **Tags:** compliance, billing, france, positioning

## Context

Issue #141 asks whether an open-source, self-hosted product can be
homologated to produce *feuilles de soins électroniques* (FSE), and
what is minimally useful if not. Sources: GIE SESAM-Vitale's public
pages for éditeurs (cahier des charges, technologies supportées,
éditeurs PS libéraux, home page), the CNDA (Centre national de dépôt
et d'agrément of the Assurance Maladie) "référencer un logiciel" mode
opératoire, the ANS pages on HDS and on the Ségur programme for
chirurgiens-dentistes. Points not confirmed from those are marked
**open**.

### 1. What producing an FSE requires

Two gates, both attached to a **publisher and a version**:

1. **CNDA agrément.** The publisher "télécharge et signe le contrat de
   service proposé par le CNDA (protocole d'agrément SESAM-Vitale,
   conditions générales et particulières)", receives a *Numéro
   d'Identification Éditeur* (NIE) giving access to the test
   resources, develops against the GIE's reference documents,
   validates on the CNDA test environments, submits a *dossier de
   recette*, then passes the CNDA's own test sessions (on site or
   remote, "la base intégrale du guide de tests"), repeated until
   compliant. "L'attestation de conformité du CNDA est délivrée au
   logiciel pour un n° de version donné" and the version is published
   on the CNDA site.
2. **GIE SESAM-Vitale homologation** (Commission de Validation et
   d'Homologation, CVH) of the integration of the GIE's *composants
   SESAM-Vitale* per the *Cahier des charges Éditeurs*, currently
   **CDC 1.40 – Addendum 8 (April 2025)**, covering FSE/DRE, Vitale
   card reading, e-prescription, INSi and ADRi. The components are
   distributed by the GIE through its *espace industriels* (access on
   request) and support Windows, macOS and Linux 64-bit, plus Citrix;
   they run on the workstation that holds the card reader (PC/SC,
   homologated readers) and the professional's CPS/e-CPS.

For liberal professionals (dentists included) the expected service
set is FSE, DRE, tiers payant, ADRi, ALDi, SCOR, e-prescription,
AATi/DMTi/IMTi, INSi, DMP, HRi and Vitale card update (TMAJ). No
dentist-specific derogation appears on the GIE pages.

Costs of the CNDA contract and of the component licence are not
published on the pages read — **open** (they are commonly described
as free of charge, but no official text was found saying so).

### 2. Does open source, self-hosted, fit?

Nothing forbids an open-source publisher from signing the CNDA
contract. What does not fit is *self-hosted and modifiable*:

- the agrément and the homologation are per version; a practice that
  runs a modified build runs an unagreed version, exactly as in
  Portugal (ADR 0027);
- the SESAM-Vitale components are proprietary binaries licensed to
  the publisher; they cannot be committed to a public repository, so a
  self-hosted build would have to fetch them from the GIE at install
  time under the publisher's licence — **open** whether the licence
  allows that distribution model;
- the components, the reader and the CPS live on the workstation, so
  a browser-based product needs a local agent per workstation (the
  way web-based LGCs do it), which is a second deliverable to
  homologate.

The realistic route for a project like this is therefore the one the
market already uses: **integrate a homologated *moteur de facturation
SESAM-Vitale*** from a specialised vendor (several exist; the GIE
lists them among éditeurs), where the engine vendor holds the
homologation and DentalPin is the LGC feeding it. Whether the LGC
still needs its own CNDA attestation when it drives such an engine is
**open** on the CNDA pages; the engine vendors' editor programmes
settle it contractually (Decision 2).

### 3. Beyond FSE: HDS and Ségur

- **HDS** (art. L.1111-8 Code de la santé publique; référentiel
  approved by the arrêté of 26 April 2024): any third party hosting
  health data for a French practice must be HDS-certified; a
  practice hosting its own system for its own patients is **not**
  subject to it. That is the line the issue asked us to write down:
  self-hosted DentalPin needs no HDS; any DentalPin-operated hosting
  for French practices does.
- **Ségur du numérique, vague 2, LGC chirurgiens-dentistes**: state-
  funded (SONS) referencing of practice software on INS, DMP feeding,
  MSSanté, Pro Santé Connect and e-prescription. The dentist LGC
  dispositif is still being prepared by the ANS; the ASP guichet that
  opened in February 2026 covers the médecin de ville LGC only, so
  the dentist window has no published date — **open**. It is an
  incentive for the publisher and an expectation of the market, not a
  legal condition for a practice to use a given software.

## Decision

1. **DentalPin does not pursue SESAM-Vitale homologation as a
   self-hosted open-source product.** The gates are per publisher and
   per version, rest on proprietary workstation components, and would
   not survive a practice modifying its own build.
2. **FSE and tiers payant are reached through a homologated billing
   engine that its vendor sells as an API to LGC editors** (Stellair
   Intégral by Olaqin, Pyxvital by Pyxistem, Juxta, among others).
   The engine vendor holds the CNDA/GIE approvals, the SESAM-Vitale
   components, the card reader integration and the CPS/e-CPS; the
   *appli carte Vitale* on the patient's phone reduces the reader
   dependency further. DentalPin sends the patient and the acts and
   stores the returned status and NOEMIE returns. In this model the
   LGC does not fabricate the FSE, so the CNDA attestation question
   is the engine vendor's to answer in its editor contract; the
   vendor's editor programme replaces the two questions previously
   marked open for the CNDA.
3. This is a **`FR`-gated connector module (`fr_fse`)** registered
   through `BillingHookRegistry`, in the same shape as Portugal's
   connector (ADR 0027). No engine is chosen here; the first step is
   the editor programmes of the vendors above (contract, sandbox,
   price per practitioner), which is a maintainer task, not code.
4. **Prerequisite, and the work that starts now: the French
   nomenclature** — CCAM dental codes and the NGAP acts dentists
   still bill, tariffs and bases de remboursement, the three 100 %
   Santé baskets with their honoraires limites de facturation, and
   the *devis conventionnel*. Without it there is no legal devis and
   no feuille de soins, paper or electronic. This is module `fr_ccam`
   (issue #411), `FR`-gated, with no external dependency.
5. **Until the connector exists, DentalPin's position in France is
   "clinical record, schedule and billing outside the Assurance
   Maladie flow"**: invoices and paper *feuilles de soins* the patient
   sends themselves; no FSE, no tiers payant. The French pages and
   the country readiness matrix say so. This is not a long-term
   position: a dentist without télétransmission forfeits the
   convention's modernisation forfait, pays the paper contribution
   per feuille, cannot offer tiers payant to Complémentaire santé
   solidaire beneficiaries in practice, and makes patients wait weeks
   for reimbursement. Only purely aesthetic or non-conventionné
   practices live there.
6. **HDS**: self-hosted installations are out of scope of HDS; any
   hosted offer for French practices requires an HDS-certified host.
   Write this on the French pages instead of hedging.
7. Ségur referencing (INS, DMP, MSSanté, PSC) is tracked as a separate
   product decision. The engines above typically expose INSi and DMP
   too, so the connector is the natural place for it later; it does
   not change points 1–5.

## Consequences

### Good

- Clear French positioning; no more "coming soon" for a feature that
  needs a publisher programme we have not entered.
- The connector route keeps FSE reachable without owning proprietary
  components or a workstation agent, and the same hook serves
  Portugal.
- `fr_ccam` gives French practices a legal devis and correct tariffs
  before any vendor contract, and is reusable by the connector.

### Bad / accepted trade-offs

- Until the connector ships, a French practice keeps a second tool
  for billing the Assurance Maladie; DentalPin is a clinical /
  scheduling product there.
- FSE depends on a commercial vendor's engine, contract and per-
  practitioner subscription; a self-hosted user still needs that
  vendor account.
- The nomenclature seed must follow CCAM versions and convention
  tariff updates; someone owns that refresh.

## Alternatives considered

- **Enter the CNDA programme directly and homologate DentalPin.** —
  Per-version agrément on a product users rebuild themselves, plus a
  workstation agent and proprietary components in a public repo; not
  compatible with the project's model.
- **Read the Vitale card only (identity), skip FSE.** — Card reading
  uses the same licensed components and reader; it does not escape
  the programme, and INSi needs a CPS-authenticated call.
- **Stay at "billing outside the Assurance Maladie flow" for good.**
  — Leaves DentalPin usable only by a niche of French practices; the
  connector route is cheap enough to make that the wrong stop.
- **Ship nothing and say nothing.** — The issue exists because the
  hedging costs credibility; the honest sentence is the deliverable.

## How to verify the rule still holds

- The country readiness matrix and the French landing page state
  "FSE / tiers payant through a homologated engine (connector,
  pending); until then billing outside the Assurance Maladie flow;
  self-hosted installations outside HDS".
- No module under `backend/app/modules/` claims to produce an FSE
  itself; `fr_fse` only drives an engine whose vendor's homologation
  is named in its docs.
- `fr_ccam` exists before `fr_fse`; the connector consumes its codes
  and baskets instead of carrying its own.

## References

- Issue #141; issue #142 (French e-invoicing reform, separate);
  ADR 0027 (Portugal, same pattern)
- GIE SESAM-Vitale, Cahier des charges Éditeurs (CDC 1.40 Addendum 8,
  April 2025): <https://www.sesam-vitale.fr/web/sesam-vitale/cahier-des-charges>
- GIE SESAM-Vitale, Technologies supportées:
  <https://www.sesam-vitale.fr/web/sesam-vitale/technologies-supportees>
- GIE SESAM-Vitale, Éditeurs PS libéraux:
  <https://www.sesam-vitale.fr/web/sesam-vitale/ps-liberaux1>
- CNDA, Référencer un logiciel — mode opératoire:
  <https://cnda.ameli.fr/editeurs/referencer-un-logiciel/mode-operatoire/>
- ANS, HDS: <https://esante.gouv.fr/produits-services/hds>; art.
  L.1111-8 CSP; arrêté du 26 avril 2024
- ANS, Ségur du numérique pour les chirurgiens-dentistes:
  <https://esante.gouv.fr/segur/chirurgiens-dentistes>
