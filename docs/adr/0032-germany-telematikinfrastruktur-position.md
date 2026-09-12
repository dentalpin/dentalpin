# 0032 — Germany: Telematikinfrastruktur — DentalPin talks to an approved Konnektor, never is one

- **Status:** proposed
- **Date:** 2026-09-10
- **Deciders:** maintainers
- **Tags:** compliance, interop, germany, positioning

## Context

Issue #136 asks whether a self-hosted, open-source system can connect
to the Telematikinfrastruktur (TI) at all, what is minimally useful,
where the boundary sits, and what it costs a practice. Sources read:
gematik's Fachportal pages for Primärsysteme and the Konnektor
conformity confirmation, the Implementierungsleitfaden Primärsysteme
(gemILF_PS V2.29.0, 24.07.2026), the KIM-Clientmodul page, the fee
table, the TI-Gateway/Konnektor pages, the Zero-Trust concept; the BMG
Festlegung on TI financing (in force 01.07.2023) and §§ 291b, 341,
360, 378 SGB V; the KZBV pages on TI, VSDM, KIM, E-Rezept, ePA and the
SMC-B; BMV-Z Anlage 10 and 15; the LZK BW eHBA cost sheet and the BLZK
fee note. Points not confirmed from those are marked **open**.

### 1. Architecture and who needs which approval

A Zahnarztpraxis must hold (BMG Festlegung § 5 (2)): "Konnektor inkl.
gSMC-K und VPN-Zugangsdienst, ggf. in Rechenzentrum gehostet […] oder
TI-Gateway mit gematik-Zulassung", stationary eHealth-Kartenterminals
with gSMC-KT, an HBA (eHBA) per dentist and an SMC-B per practice,
each "mit gematik-Zulassung". Konnektor makers are CGM, secunet and
RISE; the gematik Zulassung fee (§ 325 SGB V) is 135 000 € for a
Konnektor, 26 000 € for an eHealth-Kartenterminal, 10 600 € for an
integrated KIM-Clientmodul. That is the certified layer.

The practice system is outside it. gematik: "Primärsysteme sind
dezentrale Clientsysteme, die von Leistungserbringern in ihrer
Einrichtung genutzt werden […]. Wichtig: Primärsysteme werden nicht
von der gematik spezifiziert und sind kein Bestandteil der
TI-Plattform." For VSDM, NFDM, eMP/AMTS and KIM gematik offers the
"Bestätigung der Konformität des Primärsystems zur
Konnektorschnittstelle": "Die Bestätigung ist kostenpflichtig und
erfolgt auf freiwilliger Basis, bietet jedoch den Vorteil, dass das
Primärsystem nach erfolgreichem Audit offiziell gelistet wird"; "Das
Entgelt für das Bestätigungsverfahren pro Fachanwendung beträgt
1800 EUR zzgl. MwSt."; since 01.07.2025 it is a two-hour video audit
(KoPS simulator sales ended 30.06.2025, its reports are no longer
accepted since 01.10.2025). E-Rezept conformity is tested with the
public Tiger test suite; ePA für alle with the public KOB test suite
(both on GitHub). The KOB is described by gematik's INA portal as
mandatory for the ePA medication list since the ePA rollout, while
§ 387 SGB V frames the procedure as "auf Antrag eines Herstellers" —
whether a PVS without KOB may legally be used for ePA is **open**.

How a PVS talks to the Konnektor (gemILF_PS): SOAP web services
discovered through `connector.sds`, events via CETP, client
authentication by HTTP-Basic or client certificate, every call carrying
MandantId / ClientSystemId / WorkplaceId / UserId; services CardService
(GetCards, RequestCard…), EventService (Subscribe), CertificateService,
EncryptionService, SignatureService (SignDocument/VerifyDocument),
AuthSignatureService (ExternalAuthenticate) and the Fachmodule
VSDService (ReadVSD), NFDService, AMTSService. KIM: "Das Clientmodul
[…] fungiert als SMTP- und POP3-Proxy"; the module is a gematik-approved
product integrated in a PVS or standalone; "Das PVS (oder ein
gewöhnlicher E-Mail-Client) ruft die KIM-Nachrichten am
KIM-Clientmodul ab"; KIM providers are gematik-approved.

Roadmap: the TI-Gateway connects practices by VPN to a data-centre
"Highspeed-Konnektor" with "Unterstützung bestehender
PVS-Schnittstellen"; "Der bislang in den Praxen eingesetzte
Einbox-Konnektor als physisches Gerät wird sukzessive durch eine
rechenzentrumsbetriebene, später auch cloud-basierte Anbindung an die
TI ersetzt"; Konnektor certificates are extended by three years,
automatically from 04.04.2025; RSA infrastructure is switched off
stepwise from 29.06.2026; TI 2.0 rests on Zero Trust and mTLS
(gemKPT_Zero_Trust V1.0.0). The Konnektor interface stays the PVS
contract for the foreseeable period; the Zero-Trust client contract is
published as a concept only.

### 2. Minimally useful scope and the mandatory dates

| Application | Rule for dentists | Sanction |
|---|---|---|
| VSDM (eGK read) | BMV-Z Anlage 10 § 5 (1): eGK "bei jeder ersten Inanspruchnahme im Quartal einzulesen"; § 291b (2) SGB V online check at first contact per quarter; Prüfungsnachweis sent with the Abrechnung as eGKO positions; VSDM 2.0 expected Q4 2026 | § 291b (5): "pauschal um 2,5 Prozent" since 01.03.2020 |
| KIM | KZBV: "Der Versand von Heil- und Kostenplänen und eAU erfolgt verpflichtend über KIM"; EBZ mandatory since 01.01.2023; eArztbrief "für Zahnarztpraxen […] nicht verpflichtend" | TI-Pauschale −50 % per missing application |
| E-Rezept | KZBV: "Seit dem 1. Januar 2024 […] verbindlich"; § 360 (2) SGB V | § 360 (17): 1 % cut until proof; KZBV: plus "Halbierung der monatlichen TI-Pauschale" |
| ePA für alle | KZBV: "Seit 1. Oktober 2025 müssen Zahnarztpraxen die 'ePA für alle' nutzen"; needs a PVS update | § 341 (6) S. 2: 1 % cut (1,3 % of practices in Q1 2026) |
| NFDM/eMP, eAU | Festlegung § 5 (1) lists them as required for the Pauschale | TI-Pauschale −50 % |

Festlegung § 4 (5): one missing application halves the Pauschale; "Bei
mindestens zwei fehlenden Anwendungen oder fehlender Anbindung an die
TI wird keine TI-Pauschale gezahlt." A Kassenpraxis therefore cannot
opt out of any of them; the daily-touch piece is VSDM, the one that
feeds billing is KIM (EBZ, eAU), and E-Rezept/ePA need QES with the
eHBA and, for ePA, the KOB question above.

### 3. The boundary

Confirmed: the practice's Konnektor (or TI-Gateway) is the certified
component that holds the VPN, the card sessions, encryption and
signatures; a PVS only calls it. DentalPin's server calls the Konnektor
over the practice LAN (or VPN) as one ClientSystem with one or more
Workplaces bound to card terminals; the browser never touches the
Konnektor. KIM is reached through an approved Clientmodul over
SMTP/POP3. DentalPin never implements VPN, gSMC-K, QES or the
Clientmodul itself.

### 4. Costs (official figures)

| Item | Value | Source |
|---|---|---|
| Erstausstattung basis (≤ 3 / 4–6 / 7–9 dentists) | 6 366,50 € / 8 369,00 € / 10 371,50 € | Festlegung Tab. 1 |
| Betriebskosten over 5 years | 7 900,00 € / 8 597,50 € / 9 062,50 € | Tab. 2 |
| monthly TI-Pauschale since 01.07.2023 | 237,78 € / 282,78 € / 323,90 € (+28,60 € per further 3 dentists) | Tab. 3 |
| Konnektor-Tauschpauschale | 2 300 € (+ 100–200 € gSMC-KT) | Tab. 7 |
| eHBA (VDA prices, LZK BW sheet 02/2021) | D-Trust 500 € per 5 years; T-Systems 24,99 €/quarter; medisign 34 € + 100 €/year; SHC 99,96 €/year | LZK BW |
| Kammer fee for eHBA issue (BLZK) | 20 € | BLZK |
| SMC-B | issued by D-Trust, medisign, T-Systems via the KZV, "in der Regel […] maximal fünf Jahren"; price "abhängig vom gewählten Anbieter" — **open** | KZV BW, KZBV |
| Konnektor / Kartenterminal street prices | "Die gematik hat keinen Einfluß auf die Preispolitik der Hersteller" — **open**; the Pauschale tables are the reimbursement basis | gematik |

## Decision

1. **DentalPin is a Primärsystem that talks to the practice's
   gematik-approved Konnektor or TI-Gateway over the published
   Konnektor interface; it is never a Konnektor, VPN-Zugangsdienst,
   Kartenterminal or KIM-Clientmodul.** Feasibility is settled by
   gematik's own words: Primärsysteme are neither specified nor
   approved by gematik, the conformity confirmation is voluntary and
   paid, and the interface guide is public.
2. **The first deliverable is module `de_ti`, `DE`-gated, in the
   `verifactu` shape: VSDM.** Konnektor endpoint, TLS client
   certificate or basic auth, Mandant/ClientSystem/Workplace/terminal
   mapping, `ReadVSD` at the first contact of the quarter, the VSD
   into the patient record, the Prüfungsnachweis stored per visit for
   the eGKO export, the Ersatzverfahren flags. No gematik confirmation
   is filed for it; the 1 800 € audit is an option once a practice
   asks for the listing.
3. **Second: KIM as transport** through an approved Clientmodul
   (SMTP/POP3), for receiving and sending signed attachments. The
   payloads that make KIM mandatory — EBZ and eAU datasets — are the
   KZBV PVS modules' business (ADR 0031) and stay with the approved
   PVS until that ADR's open questions are answered.
4. **E-Rezept and ePA are out of scope for now**: they need QES with
   the eHBA via SignatureService, the E-Rezept conformity confirmation
   (public Tiger suite, feasible later) and, for ePA, the KOB whose
   mandatory status is open. They remain with the approved PVS.
5. **Position until then: "DentalPin reads the eGK through your
   existing Konnektor (once `de_ti` ships); EBZ, E-Rezept and ePA stay
   in your KZBV-listed PVS."** With ADR 0031 this means a German
   Kassenpraxis runs DentalPin beside its PVS, and a purely private
   practice can run DentalPin alone (no TI duty without GKV billing).
6. **The website states the costs**: the TI-Pauschale table, the
   Konnektor-Tausch figure, the eHBA price band and that SMC-B and
   hardware prices are set by vendors.

## Consequences

### Good

- The feasibility question closes with a sourced "yes, as a client of
  an approved Konnektor"; no certification programme is needed to
  start.
- VSDM is the feature reception uses every day and the one whose
  sanction (2,5 %) is highest; it is reachable with public specs.
- One Konnektor client serves KIM, NFDM, QES later without a new
  architecture; the TI-Gateway keeps the same interface.

### Bad / accepted trade-offs

- Without EBZ/E-Rezept/ePA DentalPin cannot be the only system of a
  Kassenpraxis; those depend on ADR 0031 and on the KOB question.
- Testing needs a real Konnektor or TI-Gateway test account; the KoPS
  simulator is gone. Someone owns that lab.
- gematik specs move (VSDM 2.0 in Q4 2026, RSA switch-off from
  29.06.2026, Zero Trust); the module tracks a moving target.

## Alternatives considered

- **Build or embed a Konnektor / VPN-Zugangsdienst.** — 135 000 €
  Zulassung fee, hardware security modules, gSMC-K; not a software
  project of ours.
- **Skip TI and position for private practices only.** — Leaves every
  Kassenpraxis out; VSDM alone is cheap enough to do.
- **Start with KIM/EBZ because it is "the billing one".** — EBZ needs
  the KZBV PVS modules (ADR 0031); transport without payload is not
  useful.
- **File the gematik confirmation before shipping.** — Voluntary and
  1 800 € per application; listing is marketing, not a licence to
  operate.

## How to verify the rule still holds

- `de_ti` contains no VPN, gSMC-K, card-terminal or QES code; every
  cryptographic operation is a Konnektor SOAP call.
- Backend test: with a Konnektor stub, a `DE` patient's first visit in
  a quarter triggers `ReadVSD` and stores a Prüfungsnachweis; a second
  visit in the same quarter does not.
- The readiness matrix and German pages say "talks to your Konnektor;
  EBZ/E-Rezept/ePA stay in your PVS"; no page implies DentalPin is a
  TI component.

## Answers to the issue

1. **Can a self-hosted open-source system connect?** Yes. gematik does
   not specify or approve Primärsysteme; the Bestätigung is voluntary
   (1 800 € per application, audit since 01.07.2025); the interface
   guide and test suites are public. Caveats: ePA's KOB status is open
   and the KZV billing side is governed by ADR 0031.
2. **Minimally useful:** VSDM (eGK read + Prüfungsnachweis), then KIM
   transport. Mandatory dates/sanctions in Context §2.
3. **Boundary:** talk to the existing Konnektor/TI-Gateway over its
   SOAP interface; never be one (Context §3).
4. **Costs:** Context §4 — 237,78–323,90 € monthly Pauschale covers
   Konnektor, terminals, cards and operation; eHBA ≈ 100 €/year; SMC-B
   and hardware prices vendor-set (open).

## Open questions

- Is a KOB certificate a legal prerequisite for a PVS to be used for
  ePA für alle, or only for gematik listing? (INA says mandatory for
  eML; § 387 SGB V says "auf Antrag".)
- SMC-B and Konnektor/terminal prices from an official source.
- Whether a TI-Gateway test tenant is available to non-listed PVS
  vendors now that KoPS is discontinued.

## Readiness matrix row

See ADR 0031 — one Germany row covers both ADRs; the interop cell reads:
"❌ TI: DentalPin talks to the practice's gematik-approved
Konnektor/TI-Gateway, never is one; `de_ti` (VSDM first, KIM transport
second) pending; EBZ/E-Rezept/ePA stay with the approved PVS (ADR 0032)".

## References

- Issue #136; ADR 0031; `backend/app/modules/verifactu/` (module shape)
- gematik Fachportal, Primärsysteme: <https://fachportal.gematik.de/hersteller-anbieter/primaersysteme>
- gematik, Bestätigung Konnektorschnittstelle: <https://fachportal.gematik.de/hersteller-anbieter/primaersysteme/best-konf-ps-konnektor>
- gemILF_PS V2.29.0: <https://gemspec.gematik.de/docs/gemILF/gemILF_PS/latest/index.html>;
  gemSpec_Kon: <https://gemspec.gematik.de/docs/gemSpec/gemSpec_Kon/latest/>
- gematik KIM-Clientmodul: <https://fachportal.gematik.de/hersteller-anbieter/komponenten-dienste/kim-clientmodul>
- gematik fee table: <https://fachportal.gematik.de/schnelleinstieg/downloadcenter/zulassungs-bestaetigungsantraege-verfahrensbeschreibungen/kosten>
- gematik TI-Gateway: <https://www.gematik.de/telematikinfrastruktur/ti-zugang/ti-gateway>;
  Konnektoren: <https://www.gematik.de/telematikinfrastruktur/ti-zugang/konnektoren>;
  TI-Zugang (Fachportal): <https://fachportal.gematik.de/telematikinfrastruktur/ti-zugang>;
  Zero Trust: <https://gemspec.gematik.de/docs/TI2.0/gemKPT_Zero_Trust/gemKPT_Zero_Trust_V1.0.0/>;
  TI FAQ: <https://www.gematik.de/anwendungen/telematikinfrastruktur/faq>
- gematik INA, KOB: <https://www.ina.gematik.de/kig/konformitaetsbewertung/eml>;
  § 387 SGB V: <https://www.gesetze-im-internet.de/sgb_5/__387.html>
- BMG Festlegung TI-Finanzierung (01.07.2023): <https://www.kzbv.de/wp-content/uploads/festlegung-bmg-bmvz-anl-11-11a-11b-11d-2023-11-01.pdf>;
  § 378 SGB V: <https://www.gesetze-im-internet.de/sgb_5/__378.html>
- § 291b SGB V: <https://www.gesetze-im-internet.de/sgb_5/__291b.html>;
  § 341 SGB V: <https://www.gesetze-im-internet.de/sgb_5/__341.html>;
  § 360 SGB V: <https://www.gesetze-im-internet.de/sgb_5/__360.html>
- KZBV TI: <https://www.kzbv.de/zahnaerzte/digitales/telematikinfrastruktur-ti/>;
  VSDM: <https://www.kzbv.de/zahnaerzte/digitales/digitale-anwendungen/versichertenstammdatenmanagement/>;
  KIM: <https://www.kzbv.de/zahnaerzte/digitales/digitale-anwendungen/kommunikation-im-medizinwesen/>;
  E-Rezept: <https://www.kzbv.de/zahnaerzte/digitales/digitale-anwendungen/elektronisches-rezept/>;
  ePA für alle: <https://www.kzbv.de/zahnaerzte/digitales/elektronische-patientenakte-epa/epa-fuer-alle/>;
  SMC-B: <https://www.kzbv.de/elektronischer-praxisausweis.1119.de.html>
- BMV-Z Anlage 10 § 5 (eGK), Anlage 15 (EBZ): see ADR 0031 references
- LZK BW eHBA Anbieter und Kosten (02/2021): <https://lzk-bw.de/fileadmin/user_upload/1.Zahn%C3%A4rzte/20.Mitgliedschaft_in_der_Kammer/21.eHBA/Anbieter_und_Kosten_eHBA_Stand_LZK_BW_26.02.2021.pdf>;
  BLZK eHBA: <https://www.blzk.de/blzk/site.nsf/id/pa_ehba.html>;
  KZV BW SMC-B: <https://www.kzvbw.de/zahnaerzte/praxis/telematik/praxisausweis-smc-b/>
