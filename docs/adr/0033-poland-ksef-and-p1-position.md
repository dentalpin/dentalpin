# 0033 — Poland: KSeF barely touches a dental practice; P1 / EDM is the real ask, and it is open to us

- **Status:** proposed
- **Date:** 2026-09-12
- **Deciders:** maintainers
- **Tags:** compliance, billing, interop, poland

## Context

Issue #143 asks seven things before any code: the KSeF timetable, format and
authentication; whether a self-hosted installation may submit on its own
behalf; what comes back and what must be stored; which documents a dental
practice must produce as EDM and in what format; how software authenticates
against P1 and **whether EDM participation needs a certification an
open-source self-hosted product cannot obtain** — with the instruction that a
"no" scopes Poland down to KSeF; whether e-recepta and e-skierowanie bind
dentists; and whether NFZ reporting is in scope at all.

Sources are primary: the VAT act and the three acts that build and twice
postpone mandatory KSeF; MF's KSeF pages, the FA(3) brochure, MF's own API
documentation and SDK repositories, and a KAS training deck written for medical
professions; the act on the information system in health care (ustawa o SIOZ),
the EDM regulation, CeZ's minimum requirements for Systemy Usługodawców and the
P1 integrator pages; the cash-register regulations; NFZ's reporting and eWUŚ
pages. Everything cited below is quoted from those; points not confirmed there
are marked **open**.

### 1. KSeF — what it is, and when it bites

KSeF is the state clearing house for invoices, "służącym w szczególności do:
wystawiania, otrzymywania, dostępu, przechowywania faktur ustrukturyzowanych",
and "Każdej wystawionej w KSeF fakturze system przydziela automatycznie
unikatowy numer identyfikujący (numer KSeF)". The timetable has slipped twice:
Dz.U. 2023 poz. 1598 set 1 July 2024, Dz.U. 2024 poz. 852 replaced that with
"z dniem 1 lutego 2026 r.", and Dz.U. 2025 poz. 1203 staged it:

| From | Who | Instrument |
|---|---|---|
| 2026-02-01 | 2024 sales with VAT above 200 000 000 zł | art. 145l |
| 2026-04-01 | everyone else ("od 1 kwietnia 2026 r. dla pozostałych przedsiębiorców") | art. 145l a contrario |
| 2027-01-01 | those invoicing ≤ 10 000 zł a month, on paper/e-invoice until 2026-12-31 | art. 145m |
| 2027-01-01 | penalties: up to 100 % of the VAT shown, or 18,7 % of the gross on an exempt invoice | art. 106ni, deferred by poz. 1203 |

Cash-register invoices and paragony treated as simplified invoices up to 450 zł
stay outside KSeF until 2026-12-31 (art. 145n). Structured invoices are held in
KSeF "przez okres 10 lat, licząc od końca roku, w którym zostały wystawione".

### 2. The decisive rule — a dental clinic invoices natural persons

art. 106ga ust. 1: "Podatnicy są obowiązani wystawiać faktury ustrukturyzowane
przy użyciu Krajowego Systemu e-Faktur." ust. 2: "Obowiązek […] nie dotyczy
wystawiania faktur: […] **4) na rzecz nabywcy towarów lub usług będącego osobą
fizyczną nieprowadzącą działalności gospodarczej**"; ust. 3: in that case
"wystawia się faktury elektroniczne lub faktury w postaci papierowej". The 2025
act widened ust. 4 so consumers may *optionally* be invoiced through KSeF. MF:
"Zarówno przed 1 lutego 2026 r. jak i po tej dacie wystawianie faktur B2C […]
w KSeF jest dobrowolne"; the KAS deck adds the consequence for a doctor —
"Osobie fizycznej, która zażądała faktury i wystawiono ją w KSeF należy fakturę
przekazać w sposób uzgodniony."

This is Italy's art. 10-bis question with the opposite answer. Italy **forbids**
sending patient invoices to the SdI (ADR 0025); Poland merely does not require
it. The art. 106s exclusions regulation does not mention medical services, so
ust. 2 pkt 4 is the only door — and it covers nearly all of a dental practice's
invoicing.

### 3. Format, transport, identity

**FA(3)** replaced FA(2) on 2026-02-01; the pattern was published in the ePUAP
repository on 2025-06-25 and the XSD sits in MF's own repository. Exempt lines
use rate `zw` plus `Adnotacje/Zwolnienie`: `P_19` = "1" and `P_19A` — "należy
wskazać przepis ustawy albo aktu wydanego na podstawie ustawy, na podstawie
którego podatnik stosuje zwolnienie od podatku". A consumer buyer is
`Podmiot2/DaneIdentyfikacyjne/BrakID` = "1"; the brochure names exactly that
case.

**Authentication:** "Możliwe sposoby uwierzytelnienia w systemach zewnętrznych
to: podpis kwalifikowany, pieczęć kwalifikowana, token albo certyfikat KSeF."
Flow: `POST /auth/challenge` → a XAdES-signed `AuthTokenRequest` or an
RSA-OAEP-encrypted KSeF token → `/auth/token/redeem` → short-lived `accessToken`
plus a 7-day `refreshToken`. A certyfikat KSeF "jest nośnikiem tożsamości
podmiotu uwierzytelniającego", comes as `Authentication` or `Offline`, lasts at
most two years, and "może zostać złożony wyłącznie 'we własnym imieniu'".

**Sending:** a session declares the schema version and a 256-bit AES key wrapped
RSAES-OAEP/SHA-256 under MF's public key; XML is AES-256-CBC/PKCS#7; sessions
live 12 h; UPO comes per invoice and per session; rate limits are per (context
NIP, IP) with HTTP 429. Three environments — TEST (self-signed certificates
accepted, shared data), DEMO and PRD — each serve an OpenAPI 3.0.4 contract.

**Moment of issue (online):** "fakturę uznaje się za wystawioną w dacie jej
przesłania do KSeF (o ile data wskazana w polu P_1 jest zgodna z datą przesłania
pliku xml faktury do KSeF)". The numer KSeF is 35 characters,
`NIP-RRRRMMDD-<12 hex>-<CRC-8>`, polynomial 0x07. **Offline** has three modes:
`offline24` (the taxpayer's free choice, send by the next business day,
art. 106nda), `offline` (announced unavailability, art. 106nh) and `awaryjny`
(announced failure, 7 business days, art. 106nf); offline invoices carry KOD I
to verify the invoice and KOD II to prove the issuer via an `Offline` certyfikat.

**Certification of software: none.** The statute conditions issuing on the
*taxpayer's* authentication (art. 106nb); art. 106gb ust. 1–2 only require
"oprogramowanie interfejsowe" whose address MF publishes. MF: "Można się z nim
łączyć korzystając z API udostępnionego przez Ministerstwo Finansów i z jego
pomocą zintegrować posiadane oprogramowanie finansowo-księgowe." No
accreditation, vendor register or approval appears in any page read.

### 4. Cash register, and what a patient invoice must carry

Sales to natural persons go on a cash register (art. 111 ust. 1) and dentists
have no exemption: § 4 ust. 1 pkt 2 lit. f of the regulation of 17.12.2024
removes "opieki medycznej świadczonej przez lekarzy i lekarzy dentystów" from
every zwolnienie. They moved to online registers on 2021-07-01 (art. 145b
ust. 1 pkt 3 lit. d set 31.12.2020, extended by Dz.U. 2020 poz. 1059; KAS deck:
"Od 1 lipca 2021 roku, wszyscy lekarze muszą korzystać z kas fiskalnych
online"). An invoice is owed to a patient only on request, within three months
of the end of the month of service (art. 106b ust. 2–3), and alongside a
registered sale the issuer keeps "numer dokumentu oraz numer unikatowy kasy
rejestrującej zawarte na paragonie fiskalnym" (art. 106h ust. 1 in the wording
that takes over on 2026-02-01). If the buyer is a business the NIP must be on
the paragon *before* it prints — art. 106b ust. 5 permits an invoice only
"jeżeli paragon […] zawiera numer, za pomocą którego nabywca […] jest
zidentyfikowany na potrzeby podatku", with a 100 % penalty in ust. 6. There is
no lawful add-the-NIP-later path.

The exemption is not one provision but four, and they sit on different lines of
the same invoice: art. 43 ust. 1 pkt 19 lit. a for treatment by a "lekarz
i lekarz dentysta"; pkt 18 where the practice is a podmiot leczniczy; pkt 19a
for a third-party medical service re-billed to the patient; and **pkt 14** for
"dostawę protez dentystycznych lub sztucznych zębów przez dentystów oraz
techników dentystycznych" — a crown or denture supply is *not* pkt 19. Purely
cosmetic work qualifies under none; KAS warns the exemption fails for "medycyna
estetyczna […] bez uzasadnienia medycznego". Whichever applies, art. 106e
ust. 1 pkt 19 makes the basis mandatory and art. 106e ust. 4 pkt 3 does not drop
it; the reduced exempt form in the regulation of 29.10.2021 confirms it from the
other side — date, number, parties, service, quantity, unit price, total, plus
"wskazanie przepisu ustawy […] zgodnie z którą podatnik stosuje zwolnienie".

### 5. P1 / EDM — what a dental practice owes

"Usługodawcy są obowiązani prowadzić elektroniczną dokumentację medyczną"
(art. 11 ust. 1 ustawy o SIOZ), in the formats published in the minister's BIP,
and must exchange it to the published standards. An *usługodawca* is any
świadczeniodawca under art. 5 pkt 41 ustawy o świadczeniach — a private dental
practice with no NFZ contract included. Two dated duties bind it (art. 56):
medical events to SIM "od dnia 1 lipca 2021 r." (ust. 2a) and the ability to
exchange EDM through SIM from the same date (ust. 4). Medical events are
reported "niezależnie od źródła jego finansowania".

EDM types are closed by the regulation of 8 May 2018: nine items, of which a
dental practice realistically produces **one** — § 1 pkt 5, "opis badań
diagnostycznych, innych niż wskazane w pkt 4", where a pantomogram or CBCT
description lands. pkt 2 ("informacja dla lekarza kierującego") applies to a
specialist dental clinic taking referrals; the rest are hospital, laboratory,
school-nurse or rescue documents. Recepty and skierowania are EDM by statutory
definition (art. 2 pkt 6 lit. a and c).

**e-recepta** has been mandatory since 2020-01-08 (art. 56 ust. 2 — paper "do
dnia 7 stycznia 2020 r.") and binds a lekarz dentysta like any prescriber. One
class has **no fallback at all**: since 2023-11-01, art. 95b ust. 1a Prawa
farmaceutycznego makes prescriptions for substances in grupy II-N, III-P and
IV-P electronic-only, and the "brak dostępu do systemu" escape in ust. 2 does
not reach it. Codeine analgesics and the benzodiazepines used for sedation are
in daily dental use, so P1 availability is a hard dependency for that class.

**e-skierowanie** became mandatory on 2021-01-08, but only for the types listed
in the regulation of 15 April 2019 — publicly funded specialist care, hospital
admission, CT/MR and a few others. A routine private dental referral is not
among them, but CeZ's FAQ (v3.02, 2021-01-20, Q45) confirms the hospital limb
reaches every dentist: "lekarze, którzy nie podpisali umowy z NFZ, mogą […]
wystawić e-skierowanie na leczenie szpitalne (każdy lekarz, lekarz dentysta,
felczer)". A referral in SIM is immutable — art. 59aa ust. 6: "Treść
skierowania zapisanego w SIM nie może być zmieniana […] zostaje anulowane
w SIM […] a zmiana treści […] następuje przez wystawienie nowego skierowania."

### 6. How software connects to P1 — and who certifies it

CeZ's minimum requirements for Systemy Usługodawców (v2.0, 2021-06-18), issued
under art. 8b ustawy o SIOZ, are the contract: "System Usługodawcy musi mieć
możliwość utworzenia dokumentu XML zgodnie z przyjętym w kraju standardem
Polskiej Implementacji Krajowej HL7 CDA, a następnie, odpowiednio przesłać albo
zaindeksować do Systemu P1." The current specification is PIK HL7 CDA 1.3.2
(2020-06-30), which defines "Opis badania diagnostycznego" among others. The
version number has not moved since 2020, but the specification has: CeZ keeps
publishing dated template packages under the same 1.3.2 base (Patient Summary
2025-05-30, orzeczenie w medycynie pracy 2026-01-08), each starting its own
nine-month adoption clock under art. 8b — so "we target PIK 1.3.2" is not a
conformance statement; the announcement feed is. PIK carries three dental
artefacts, none a document type: the value set "Specjalizacja lekarza dentysty"
(OID `2.16.840.1.113883.3.4424.13.11.22`), admitted only in the two recepta
author templates; the profession code `LEKD`; and one imaging dictionary entry
for a dental CT. A praktyka zawodowa identifies itself by its RPWDL księga
rejestrowa number, a hyphen and the Lp. of the rodzaj działalności.

Transport is SOAP with WS-Security X.509 Certificate Token Profile over mutually
authenticated TLS: "system zewnętrzny zobowiązany jest użyć certyfikatu do
uwierzytelnienia systemu wydanego przez Centrum Certyfikacji P1", and the SOAP
message is signed with a second (WSS) certificate. Both are issued **to the
practice**, not to a vendor, through RPWDL 2.0. Medical events run over FHIR;
the EDM index is IHE XDS.b — ITI-42 register, ITI-18 search, ITI-57 update and
an ITI-20 log channel. The practice keeps its own EDM repository; P1 holds the
index and the mapping from repository identifier to a retrieval endpoint.
Documents are signed with a qualified signature, Profil Zaufany, podpis osobisty
(e-Dowód) or the free ZUS mechanism — all the *dentist's* credentials, none a
server secret.

**The answer to the issue's point 5 is yes.** The integration environment opens
on request — "W celu uzyskania dostępu do środowiska INT należy wysłać do CeZ
wypełniony wniosek" — after which CeZ issues an integrator TLS certificate. The
Projectathon, CeZ's integration-test workshop for gabinet and apteka software,
is voluntary and yields a published list of vendors who passed: marketing, not a
licence. No provision read makes a producer's registration or certification a
condition of connecting. What is **open** is whether CeZ grants INT access to a
producer with no Polish legal entity.

### 7. NFZ

Reporting is deliberately vendor-neutral. § 10 of the Minister of Health's
regulation of 26.06.2019 requires data "w formacie komunikatów elektronicznych"
per the annexed message descriptions; NFZ publishes every komunikat (SWIAD,
DEKL, KOL, UMX, FZX, LIOCZ…) as a free download under zarządzenia issued on
art. 102 ust. 5 ustawy o świadczeniach; and an oddział states the position
outright: "Z punktu widzenia Oddziału NFZ nie ma znaczenia, jaka aplikacja
wygenerowała komunikat" and "NFZ nie prowadzi testów ani rankingów aplikacji
posługujących się formatem otwartym" — the open format following from the 2005
informatisation act's requirement of equal treatment of IT solutions. eWUŚ
likewise publishes a WSDL, a test endpoint, a versioned interface document and a
SoapUI project for "twórcy oprogramowania". **No NFZ certification of practice
software exists.**

What stops us is surface, not permission. Settlement presupposes an umowa in
rodzaj *leczenie stomatologiczne*, whose conditions and point catalogue move
with zarządzenia Prezesa NFZ several times a year (base 60/2023/DSOZ, amended
through 44/2025/DSOZ and later); the provider portal is region-dependent (eight
oddziały on SZOI, eight on Portal Świadczeniodawcy); transport is per-oddział
mailboxes rather than an API; test environments exist at only two oddziały; and
tendering runs on paper or a data carrier through NFZ's own Ofertowanie
application, so it is not integrable at all. eWUŚ adds its own constraint:
credentials are per human operator and "Zabrania się udostępniania osobom
trzecim loginu i hasła", now with TOTP. That is a product, not a module.

## Decision

1. **Two `PL`-gated modules, sized by the evidence, not symmetrically.**
   `pl_ksef` is small and feasible today; `pl_p1` is the large one and the first
   country module here that hangs off the clinical record rather than `billing`.
   The issue's instinct — two modules, not one — is adopted.
2. **`pl_ksef` is a billing compliance module in the `verifactu` shape**: own
   `pl_ksef_*` tables, own Alembic branch, own Nuxt layer, registered through
   `BillingHookRegistry` on `PL`, uninstall round-trip test. `billing` learns
   nothing about Poland.
3. **It sends only invoices whose buyer is a podatnik or an osoba prawna**
   (art. 106ga ust. 1). Invoices to natural persons are never queued; the hook
   decides from the recipient's fiscal identity, not a checkbox. Because
   art. 106ga ust. 4 now permits it, a per-clinic opt-in for consumer invoices
   exists — **default off**. Putting a named patient and a treatment description
   into a state repository for ten years is the practice's decision, and never
   the path of least resistance.
4. **FA(3) only**, validated against the official XSD in tests: rate `zw`,
   `P_19` = "1" with `P_19A` carrying the basis, `Podmiot2/BrakID` = "1" when
   the opt-in is used. **The exemption basis is a per-catalog-item attribute,
   not a clinic-wide constant** — pkt 19 lit. a for treatment, pkt 18 for a
   podmiot leczniczy, pkt 19a for a re-billed service, pkt 14 for a prosthesis,
   none for cosmetic work, which is taxed. The same field drives the PDF.
5. **Transport is KSeF API 2.0 with the clinic's own identity** — an
   `Authentication` certyfikat KSeF or a KSeF token, stored encrypted per
   clinic; never a DentalPin-held credential, never a DentalPin-operated
   service. TEST/DEMO/PRD switchable like verifactu's environments. The module
   stores the sent XML, the numer KSeF, the UPO and every rejection immutably
   and mirrors state into `Invoice.compliance_data['PL']`. KOD I goes on the PDF.
6. **`offline24` is the failure mode, not an error path.** If the send fails the
   invoice is still issued with its own P_1 date, flagged `offlineMode: true`,
   and drained by the next business day. KOD II, and the `Offline` certyfikat it
   needs, is a second phase.
7. **No certification is sought, because none exists.** Poland is the first
   country ADR whose answer to "may a self-hosted, modifiable, open-source
   product submit on its own behalf?" is an unqualified yes — contrast Portugal
   (ADR 0027) and Germany (ADR 0031).
8. **The cash register stays outside DentalPin.** We are not a fiscal device and
   never drive one. `pl_ksef` records the paragon's document number and the
   kasa's unique number against the invoice, and the UI asks for a business
   buyer's NIP *before* the paragon is taken (art. 106b ust. 5).
9. **`pl_p1` ships in three phases:** (a) zdarzenia medyczne over FHIR plus the
   EDM index over IHE XDS.b, the duty live since 2021-07-01 that binds private
   practices too; (b) EDM production — "Opis badania diagnostycznego" in PIK
   HL7 CDA, with the practice-side repository and the retrieval endpoint P1
   indexes; (c) e-recepta, and e-skierowanie only for the listed referral types.
   Poland is **not** scoped down to KSeF. Three constraints are fixed now
   because they shape the data model: a skierowanie in SIM is never edited, only
   cancelled and reissued; an e-recepta for a II-N/III-P/IV-P substance has no
   paper mode, so `pl_p1` must surface P1 unavailability to the prescriber
   rather than degrade silently; and conformance tracks CeZ's dated PIK template
   packages on the art. 8b nine-month clock, not the frozen "1.3.2" label.
10. **DentalPin never holds a dentist's signing credential.** Signing is done
    with the dentist's qualified certificate, Profil Zaufany, e-Dowód or the ZUS
    mechanism; `pl_p1` hands the document out to be signed and takes the signed
    XML back — the Polish form of ADR 0032's rule that we talk to the trusted
    component and are never it. The P1 TLS and WSS certificates are the
    clinic's, obtained through RPWDL 2.0 and held as module settings.
11. **NFZ settlement is out of scope for a first version**, confirming the
    issue's instinct. eWUŚ is the one cheap piece and the natural seed of a
    later `pl_nfz`, on the condition that each user supplies their own operator
    login and TOTP and the system never stores a shared one. Tendering is never
    in scope.
12. **Position until the modules ship:** "DentalPin holds the clinical record,
    schedule and invoicing for a Polish practice; patient sales still go through
    your own kasa fiskalna online, and KSeF only matters for the invoices you
    issue to businesses." Stated on the Polish pages and in the readiness matrix.

## Consequences

### Good

- Poland is the cheapest compliance market we have examined: no certification,
  no accredited intermediary, no per-version approval, a published OpenAPI
  contract and three environments, one accepting self-signed certificates.
- Scoping `pl_ksef` to B2B keeps it genuinely small and keeps patient health
  data out of a state repository by default.
- `pl_p1` gives the project its first clinical-interop module and a reusable
  answer for later markets that ask the record, not the invoice, to interoperate;
  the signature boundary repeats ADR 0032's, so that rule now has two precedents.

### Bad / accepted trade-offs

- `pl_p1` is large: FHIR, IHE XDS.b, CDA templates, an OID registry, a versioned
  document repository and an audit-log feed. It needs an owner who can test
  against INT, and the II-N/III-P/IV-P prescription class gives it an
  availability requirement no other module here carries.
- A Polish practice still runs a kasa fiskalna beside DentalPin.
- FA(3), the API contract and the PIK template packages all move.
- An NFZ-contracted practice keeps its NFZ reporting elsewhere — most Polish
  dental practices by volume.

## Alternatives considered

- **One `pl_compliance` module.** — Invoicing and clinical interop share only
  the country: different tables, credentials, cadence and owners. Rejected for
  the reason ADRs 0025 and 0026 split Italy.
- **Send patient invoices to KSeF by default.** — Permitted since 2025, but it
  puts a named patient and a treatment description in a ten-year state archive
  with no obligation requiring it. Kept as opt-in.
- **Be the fiscal device / drive the kasa.** — A different certification regime
  (Centralne Repozytorium Kas, homologated hardware) for no clinical gain.
- **Scope Poland down to KSeF**, as the issue offers if certification blocks
  EDM. — The premise fails; it would leave the harder, more valuable half undone.
- **Start `pl_p1` with e-recepta.** — Most visible, but it needs a qualified
  signature per dentist and a prescription model built for one market. Zdarzenia
  medyczne plus the EDM index already binds every practice and needs no new
  clinical modelling.
- **Build `pl_nfz` first.** — Formats are public, but settlement is bound to an
  umowa, a per-oddział portal and a moving catalogue.

## How to verify the rule still holds

- Backend test: a `PL` invoice to a natural person is not queued while the
  consumer opt-in is off; with the opt-in on it is queued with
  `Podmiot2/BrakID` = "1".
- Backend test: a `PL` exempt line renders `zw` with `P_19` = "1" and the item's
  own basis in `P_19A` — a prosthesis line pkt 14, a treatment line pkt 19
  lit. a; issuing fails if any exempt item has no basis. Every payload validates
  against the committed `schemat_FA(3)_v1-0E.xsd` fixture.
- Backend test: `pl_p1` refuses an e-recepta for a II-N/III-P/IV-P product while
  P1 is unreachable and never offers a paper path for it; a skierowanie edit
  produces a cancellation plus a new document.
- Grep: no module writes a fiscal receipt, drives a kasa rejestrująca or stores a
  dentist's signing key; every signature in `pl_p1` is an inbound signed
  document. Neither module adds columns to core, `billing`, `patients` or
  `clinical_notes`; both uninstall clean.
- `docs/technical/country-readiness.md` and the Polish landing page carry the
  sentence in Decision 12.

## Answers to the issue

1. **Dates** — §1: 2026-02-01 above 200 mln zł, 2026-04-01 for the rest, the
   ≤ 10 000 zł/month and cash-register carve-outs to 2026-12-31, penalties from
   2027-01-01; two postponements, each cited.
2. **Format, authentication, self-hosted submission?** — §3: FA(3), KSeF API
   2.0, XAdES or KSeF token, certyfikat KSeF, three public environments. Yes,
   and there is no certification to obtain.
3. **What comes back, what to store** — §3, Decision 5: numer KSeF and UPO,
   session and per-invoice statuses, rejections; we store the sent XML, number,
   UPO and every rejection. KSeF keeps the invoice 10 years.
4. **Which EDM, in which format** — §5: in practice one, "opis badań
   diagnostycznych", in PIK HL7 CDA; plus e-recepta and e-skierowanie as
   statutory EDM; plus the medical-event report binding every practice since
   2021-07-01.
5. **P1 authentication; certification?** — §6: mutually authenticated TLS with a
   CeZ certificate plus a WSS signature, both issued to the practice through
   RPWDL 2.0; integration access on a wniosek; Projectathon voluntary.
   **Nothing blocks us**, so Poland is not scoped down.
6. **e-recepta / e-skierowanie for dentists?** — §5: e-recepta yes since
   2020-01-08, electronic-only with no paper fallback for II-N/III-P/IV-P
   substances since 2023-11-01. e-skierowanie only for the listed types, so rare
   in private dentistry — but every dentist issues one when referring for
   hospital treatment.
7. **NFZ in scope?** — §7, Decision 11: separate and substantial. Permission is
   not the problem (open formats by law; NFZ neither tests nor ranks provider
   software) but the portal split, mailbox transport, scarce test environments
   and a moving catalogue make it a product. Out of scope; eWUŚ is the exception.

## Open questions

- Whether CeZ opens the P1 integration environment to a producer with no Polish
  legal entity, and on what terms — **not established**.
- Whether a dental "opis badania diagnostycznego" has a narrower template than
  the general one — **not established**.
- Whether CBCT (tomografia stożkowa) counts as "tomografia komputerowa" in the
  e-skierowanie regulation, whose CT limb reaches **privately financed** scans.
  If it does, a cash-pay implantology practice is inside mandatory
  e-skierowanie. **Not established** — a question for CeZ, not for inference.
- Whether MF or UODO has published any position on health-related content in
  consumer invoices sent voluntarily to KSeF — **not established**; hence
  Decision 3 defaults the opt-in off.
- Whether an `Offline` certyfikat KSeF can be provisioned unattended for a server
  or needs an interactive MCU session each renewal — **not established** beyond
  "we własnym imieniu".
- Whether NFZ's komunikaty XML carry any licence restricting reimplementation —
  **not established**; they are published without a notice.

## Readiness matrix row

| Poland | ✅ `pl` | ❌ | ❌ KSeF: mandatory 2026-02-01 / 2026-04-01, penalties 2027-01-01 — but art. 106ga ust. 2 pkt 4 exempts invoices to natural persons, so almost every patient invoice is out of scope and KSeF matters only for B2B; `pl_ksef` pending, **no certification needed** (MF publishes the OpenAPI contract, SDKs and three environments); patient sales stay on the practice's own kasa fiskalna online (ADR 0033) | ❌ P1/EDM: **feasible for a self-hosted open-source system** — CeZ issues the TLS/WSS certificates to the practice through RPWDL 2.0, the integration documentation is public, the Projectathon is voluntary; `pl_p1` pending (zdarzenia medyczne + EDM index, then EDM production, then e-recepta/e-skierowanie); the dentist's qualified signature never leaves the dentist; NFZ settlement out of scope (ADR 0033) | #143, #144 |

## References

Every URL, with the sentence it supports and the date fetched, is in
`SOURCES.md` beside this ADR. Principal instruments:

- Issue #143; `backend/app/modules/verifactu/`, `docs/modules/verifactu.md`,
  `backend/app/modules/billing/hooks.py`; ADR 0025 (Italy SdI — the B2C
  analogue), 0026, 0027, 0031, 0032.
- **Tax:** VAT act t.j. Dz.U. 2025 poz. 775 (art. 43 ust. 1 pkt 14/18/19/19a,
  106b, 106e, 106h, 111, 145b); KSeF acts Dz.U. 2023 poz. 1598, 2024 poz. 852,
  2025 poz. 1203; kasy Dz.U. 2024 poz. 1902 and 2020 poz. 1059; reduced exempt
  invoice Dz.U. 2021 poz. 1979 — via `api.sejm.gov.pl/eli/acts/DU/<year>/<pos>`.
- **Health:** ustawa o SIOZ t.j. Dz.U. 2025 poz. 302 (art. 2, 8b, 11, 13a, 56);
  EDM regulation t.j. Dz.U. 2023 poz. 1851, amended 2025 poz. 930; art. 95b
  ust. 1a Prawa farmaceutycznego; art. 59aa ustawy o świadczeniach; świadczenia
  gwarantowane stomatologiczne t.j. Dz.U. 2025 poz. 615.
- **Portals:** <https://ksef.podatki.gov.pl/>, <https://github.com/CIRFMF/ksef-docs>,
  <https://ezdrowie.gov.pl/portal/home/dla-dostawcow/>,
  <https://www.cez.gov.pl/HL7POL-1.3.2/plcda-html-1.3.2/plcda-html/>,
  <https://www.nfz.gov.pl/dla-swiadczeniodawcy/>.
