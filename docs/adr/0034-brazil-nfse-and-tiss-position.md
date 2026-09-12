# 0034 — Brazil: nothing certifies the software, so DentalPin emits NFS-e itself and speaks TISS per operadora

- **Status:** proposed
- **Date:** 2026-09-12
- **Deciders:** maintainers
- **Tags:** compliance, billing, interop, brazil

## Context

Issue #139 asks seven things before any code: for NFS-e, national or
municipal emission and what that means for self-hosted software, the
layout, the credential, cancellation; for TISS, the current version
and cadence, which guias a dental practice sends and how the rol
relates to our catalog, and whether submission is per operadora or
standardised. Sources are the primary texts as published by the
issuing bodies: CF art. 156, LC 116/2003 and LC 214/2025 on planalto;
the CGNFS-e resolutions and the technical documentation on
gov.br/nfse; Receita Federal's 2026 guidance; ANS's TISS componentes
(Organizacional 202607, Conteúdo e Estrutura 202511, and the
Comunicação XSD/WSDL bundle, downloaded and inspected); the CFO and
CFM act repositories; the SBIS certification manual; LGPD and
Resolução CD/ANPD 15/2024. Every claim is quoted with its URL in
`SOURCES.md`. Points not confirmed from those are marked **open**.

Brazil inverts the question that decided Portugal, France and
Germany. **Nobody certifies the software** — not for invoicing, not
for claims, not for clinical records. So the question stops being
"may we?" and becomes "what must we not hard-code?", because both
regimes are mid-transition and both are versioned on a calendar.

### 1. NFS-e: municipal tax, national standard, taxpayer's key

ISS is municipal (CF art. 156, III; LC 116/2003 art. 1º). Dentistry
is list item **4.12 – Odontologia**; art. 3º puts the tax at the
provider's establishment, and dentistry is not one of its 25
exceptions. Rates run 2 %–5 % per municipality per sub-item.

The **padrão nacional** comes from a Convênio of 30.06.2022 (DOU
01.07.2022) governed by the **CGNFS-e** (5 RFB, 5 ABRASF/FNP, 5 CNM);
the model is **Resolução CGNFS-e nº 3/2023**, whose art. 3º has the
taxpayer sign and transmit a **DPS** either to the Emissor Público
Nacional or to a municipal Emissor Local, the document reaching the
**ADN** either way. NT 004 on the national path: the DPS "será
enviada à 'Sefin Nacional', responsável pela validação das
informações, cálculo dos tributos e autorização da NFS-e", returning
an NFS-e XML in which "a DPS é assinada e encapsulada no interior da
nota gerada". Transport is REST/JSON over mutually authenticated TLS
with an XSD-validated payload (`POST /nfse`, `GET /nfse/{chave}`, and
the `parametros_municipais` family).

All 5 571 entes federados have adhered, and **LC 214/2025 art. 62 §1º**
made it compulsory from 01.01.2026: a municipality must either let
taxpayers emit nationally or, keeping its own emitter, share into the
ADN in the national layout — enforced by suspending voluntary
transfers (§7º), through 31.12.2032. Adhering is not the same as
emitting nationally (NT 004 §1.1). But **Resolução CGSN nº 189/2026**
(DOU 28.04.2026) closed that gap for our users: ME and EPP optantes
pelo Simples Nacional — nearly every dental clinic — "deverão usar
obrigatoriamente o Emissor Nacional a partir de 01/09/2026", and the
CGNFS-e names the two compliant channels as the web portal **or**
"software ERP com integração … API com a SEFIN Nacional". That date
has passed: API integration discharges the obligation rather than
evading it.

**Certification — the rule, verbatim.** Resolução CGNFS-e nº 3/2023
art. 3º parágrafo único:

> "A transmissão dos arquivos digitais da DPS e da NFS-e […] será
> efetuada via internet, por meio de protocolo de segurança ou
> criptografia, com **utilização de sistema informatizado
> desenvolvido ou adquirido pelo contribuinte** ou disponibilizado
> pela administração tributária."

Art. 9º, II repeats it for events. What is authorised is the
**taxpayer**, not the program: art. 4º § único deems authorised "a
pessoa jurídica regularmente inscrita no CNPJ e não desautorizada
pelo ente federativo". The only gate is self-service — "Para emissão
via API (sistemas próprios), é necessário credenciamento prévio no
Painel do Contribuinte" — and Produção Restrita is "disponível para
todas as empresas" (NT 004 §1.2), with no approval step to production
documented (**open**). The credential is the clinic's: Manual
Integrado §§6.1.3–6.1.4 requires an **ICP-Brasil A1/A3 certificate
carrying the emitter's CNPJ**, used both as the mTLS client
certificate and to sign the DPS. (The FAQ's "não preciso de
certificado digital" is scoped to the web emitter; simple signature
is for pessoas físicas and MEI only, art. 2º §3º.) This is the mirror
image of Portugal, where the signing key had to be "de conhecimento
exclusivo do produtor do programa" (ADR 0027). Here it is the
taxpayer's by design.

**Cancellation.** Art. 7º: an issued NFS-e "não pode ser alterada,
ressalvadas as hipóteses de cancelamento ou substituição", neither
reversible. Art. 8º lists 16 events; **there is no carta de
correção** — art. 9º §2º routes correction through a new NFS-e plus
cancellation of the original. Deadlines are not national: art. 8º §2º
subordinates "os prazos" to "os critérios parametrizados pelo ente
federativo convenente no Portal Administrativo Municipal (PAM)", and
Manual Integrado §13.2.4.3 enumerates them (cancellation window in
days, value restrictions, unidentified tomador, already-collected
taxes, substitution window). They are read at runtime, alongside ISS
rates, special regimes, deductions and retentions.

### 2. The tax reform is a moving layout, not a future project

**LC 214/2025** instituted IBS, CBS and IS; IS does not reach dental
services. 2026 is a test year at IBS 0,1 % (art. 343) and CBS 0,9 %
(art. 346), both offsettable (art. 348) — Receita Federal states that
a taxpayer who issues documents correctly "estará dispensado de
recolhimento do IBS e da CBS". PIS/COFINS go on 01.01.2027 (art. 542);
ISS decays 10/20/30/40 % across 2029–2032 (art. 508 inserting LC 116
art. 8º-B — the 2029 rate is a *function* of the 31.12.2028 rate);
**LC 116 is repealed 01.01.2033** (art. 543, IV).

The layout already carries this: NT 004 v2.0 added the `IBSCBS`
groups "em atendimento às alterações previstas na Emenda
Constitucional nº 132", in production with legal validity from
05.01.2026, with `cIndOp` "baseada no art. 11 da LC nº 214". Nine
months later the annexes are at Anexo VI v1.04.00 / Anexo VII
v1.02.00 (NT 009), the production XSD is v1.01-20260209, and NT 008
rewrote the DANFSe. The groups are optional but **fully validated
when present** (NT 004 §1.1) — partial data is worse than none. And
the deadline has arrived: Ato Conjunto RFB/CGIBS nº 4/2026 makes
destaque due from **01.10.2026** for ordinary LC 116 services (alínea
"d", where 4.12 falls) and 01.01.2027 for Simples Nacional optants
who elected destaque in September 2026; omission is not a rejection
until 31.12.2026 but "evidenciará a desconformidade do documento
fiscal".

### 3. TISS: one contract, N endpoints

RN 305/2012 is revoked; **RN 501/2022** is in force (regulated by IN
ANS nº 9/2022; penalties via RN 489/2022 arts. 39 and 47). Its scope
article binds, with no segmentation carve-out, "Operadora …;
**Prestador de Serviços de Saúde**; Contratante…; Beneficiário…;
ANS" — so it binds the practice. Operadoras may not alter the
standard (item 23) nor demand a paper duplicate of a digitally signed
exchange (item 24).

Five componentes — Organizacional, Conteúdo e Estrutura,
Representação de Conceitos (TUSS), Segurança e Privacidade,
Comunicação — **each versioned separately**; there is no single "TISS
version". Julho/2026 is Organizacional 202607, Conteúdo e Estrutura
202511, TUSS 202607, Segurança 202511, Comunicação **04.03.00**
(01.06.00 is the separate operadora→ANS line). Cadence is roughly
bi-monthly (JAN, MAR, MAI, JUL 2026), and item 323 sets the window:
"não será inferior a três meses e não superior a doze meses após o
início da vigência". Two rules matter more than the version number:
item 209, "Sempre haverá no mínimo uma e no máximo duas versões do
Componente de Comunicação vigentes"; item 210, "A versão a ser
utilizada … **será a acordada entre as partes**". And item 211: a
TUSS term is validated against the **date of care**, not of
transmission.

**Transport is per operadora.** Items 133–136: operadoras "devem
dispor aos prestadores … as tecnologias de webservices e de portal";
the prestador chooses between them; each operadora must publish on
its own Portal TISS "o endereço dos webservices disponibilizados pela
operadora" and its Coordenador TISS. The downloaded WSDLs confirm it
— every `<soap:address/>` is empty. ANS standardises the contract,
never the address. Item 139 is the licence to ship: "**Qualquer
solução tecnológica poderá ser utilizada** desde que consiga atender
na íntegra as normas de todos os componentes do Padrão TISS." No ANS
registry, accreditation list or conformance seal exists for prestador
software; whether individual operadoras run their own onboarding
tests is **open**. The practice never sends to ANS — item 316 puts
the monthly submission on the operadora, on the 01.06.00 schemas.

**Which guias.** Mandatory electronic processes (item 37): cobrança,
autorização *limited to the lote de anexos*, internação/alta,
demonstrativos de retorno, recurso de glosas; optional (item 38)
elegibilidade and other authorisation — but item 41 requires any
optional process done electronically to be TISS-shaped. For a dental
practice that is: the **Guia de Tratamento Odontológico**, which does
three jobs at once ("Cobrança, solicitação de autorização … e pode
ser utilizada para comprovação de presença") and chains continuations
through "Número da Guia Principal"; the **Anexo de Situação Inicial**,
which may travel separately via LoteAnexo (item 50.5) — the mandatory
half of authorisation; the **Demonstrativo de Análise de Conta** and
**Demonstrativo de Pagamento** (dental variant, contingency guia 160);
and the **Recurso de Glosa Odontológica** (163). The Guia de
Honorários does not apply ("só pode ser vinculada à guia de
Solicitação de Internação"). Whether a dental consultation may use
the generic Guia de Consulta is **open**. Batches: LoteGuias ≤ 100 of
one type, LoteAnexo and RecursoGlosa ≤ 1.

Dental fields sit per procedure line — dente (tabela 28), região da
boca (42), face (32), whose **String 5 width means a set of faces**,
not one. Header: tipo de atendimento em odontologia (51) and tipo de
faturamento (55), mandatory; data de término do tratamento when there
was no prior authorisation. Situação inicial is per tooth against
tabela 44 plus periodontal and soft-tissue flags; the paper
contingency form is an FDI odontogram legended "A - Ausente ·
E - Extração Indicada · H - Hígido · C - Cariado · R - Restaurado",
signed by dentist and patient. **There is no "situação final"** —
closure is a date, not a second odontogram.

**TUSS is not the Rol**, which is the catalog question #135 raises
for Germany. Item 103: every Rol item is necessarily in TUSS 22, but
TUSS "também [admite] procedimentos … que, mesmo não constando no
rol, sejam praticados"; item 104 refuses any TUSS request touching
coverage. ANS publishes a TUSS↔Rol correlation spreadsheet precisely
because they are different lists. Dental codes originate in the
**CBHPO**, not the CBHPM, and each term carries início/fim de
vigência. Provider identity is per contract: CNES (mandatory,
placeholder `9999999`), CRO with UF, and a "código do contratado …
junto a operadora, **conforme contrato estabelecido**" — *N* codes
for *N* operadoras.

### 4. Clinical records: the decisive question, answered the other way

Keeping a prontuário is mandatory and may be digital — CEO (Res.
CFO-118/2012, in force; amended in art. 20 only by CFO-271/2025)
art. 17: "É obrigatória a elaboração e a manutenção … e a sua
conservação em arquivo próprio **seja de forma física ou digital**",
each entry carrying "data, hora, nome, assinatura e número de
registro do cirurgião-dentista no Conselho Regional de Odontologia".
Denying access or a copy is an infraction (art. 18, I).

Paperless operation is authorised by **Res. CFO-91/2009 art. 3º**,
and the condition is conformity, not a certificate:

> "Autorizar o uso de sistemas informatizados … **eliminando a
> obrigatoriedade do registro em papel, desde que esses sistemas
> atendam integralmente aos requisitos do 'Nível de garantia de
> segurança 2 (NGS2)'**, estabelecidos no Manual de Certificação para
> Sistemas de Registro Eletrônico em Saúde."

Art. 4º refuses the same for NGS1; CFM 1.821/2007 art. 3º is worded
identically. Three facts settle the certification question:

- **The seal was abolished.** Res. CFM 2.218/2018 (DOU 29.11.2018)
  art. 1º: "Revogar o artigo 10º da Resolução CFM nº 1.821/2007" —
  the article creating the joint selo — "CONSIDERANDO o término do
  Convênio CFM/SBIS".
- **Federal law makes certification optional.** Lei 13.787/2018
  art. 5º §2º: "**Poderão** ser implementados sistemas de
  certificação…". Requirements are delegated to a `regulamento` never
  issued (**open**); CFO's 2026 Manual reads it as the rules "de cada
  unidade de saúde ou definidos por Cirurgião-dentista".
- **SBIS says so itself.** Manual v5.0 §1: "A Certificação de S-RES
  SBIS é um **processo voluntário** que resulta em uma opinião
  técnica qualificada e imparcial". No CFO act requires it.

Where certification exists it attaches to "o nome do produto … a
versão do produto" assessed as a complete component stack, with
recertification on "adição de novas funcionalidades ou módulos fora
do escopo" — hostile to a rolling-release, self-hosted product, but
an architectural argument, not a legal bar.

**Retention:** CFO-91/2009 sets 10 years (paper) / permanent
(electronic), but **Lei 13.787/2018 art. 6º sets a 20-year federal
floor from the last entry and §5º extends it expressly to records
"gerados e mantidos originalmente de forma eletrônica"**. CFO's 2026
Manual adds Parecer 125/92 minor-tolling (10 years from the patient's
18th birthday) and recommends indefinite retention. **Signature:**
NGS2 needs one and ICP-Brasil is authorised (CFO-91/2009 art. 5º),
but MP 2.200-2/2001 art. 10 §2º does not bar "outro meio de
comprovação da autoria e integridade". **Images:** CFO-196/2019
allows publishing diagnosis and conclusion images by the treating
dentist under a TCLE (art. 2º), with name and CRO on every
publication and no third-party cases (art. 4º), and **categorically
forbids intra-procedure images and video** outside scientific
publication (art. 3º); CEO art. 44 I/XII still treats "antes e
depois" as abusive. **Teleodontologia:** CFO-278/2025 (25.11.2025,
revoking CFO-226/2020) permits teleconsulta with prescription, makes
storing session A/V optional, accepts electronic consent that
"assegure a autenticidade, integridade e rastreabilidade", and gives
the patient a right to "cópia em mídia digital".

### 5. LGPD

Health data is sensitive (art. 5º, II) and the basis for clinical
care is **not consent**: art. 11, II opens "sem fornecimento de
consentimento do titular", with "f" covering "tutela da saúde,
exclusivamente, em procedimento realizado por profissionais de
saúde", "a" carrying the retention duty and "d" the defence of
rights. A TISS claim is lawful sharing — art. 11 §4º permits it
"para permitir … II - as transações financeiras e administrativas
resultantes do uso e da prestação dos serviços", bounded by "em
benefício dos interesses dos titulares" and by §5º. Erasure does not
reach the prontuário: art. 18, VI covers only consent-based data and
is subject to art. 16, I ("cumprimento de obrigação legal ou
regulatória"); a refusal must state reasons (art. 18 §4º, II), and
the patient may demand the list of recipients (art. 18, VII).
Security is owed "desde a fase de concepção" (art. 46 §2º). Breach
notification to ANPD *and* patients is **three working days**
(Res. CD/ANPD 15/2024 arts. 6º, 9º), and a dental breach trips two
relevance triggers at once: sensitive data and professional secrecy.

## Decision

1. **Both halves are feasible for an open-source, self-hosted,
   modifiable product, and we say so plainly.** No Brazilian
   instrument certifies invoicing software (Res. CGNFS-e 3/2023
   art. 3º § único), TISS software (RN 501/2022, CO item 139) or
   clinical-record software (CFM 2.218/2018; Lei 13.787 art. 5º §2º;
   SBIS Manual v5.0). Brazil is the first market in this series where
   DentalPin can be a practice's only system. This ADR exists mainly
   so that finding is not quietly re-litigated.
2. **Two `BR`-gated modules, `br_nfse` and `br_tiss`**, in the
   `verifactu` shape: own `br_nfse_*` / `br_tiss_*` tables, own
   Alembic branch, own Nuxt layer and settings page,
   `auto_install=False`, uninstall leaves nothing behind. A practice
   that bills only particulares installs the first. `billing` and
   `catalog` learn nothing about Brazil.
3. **`br_nfse` registers a `BillingComplianceHook` for `BR` and
   targets the national path**: build and sign a DPS, `POST /nfse` to
   SEFIN Nacional, store the returned NFS-e, chave de acesso and
   DANFSe reference, mirror state into `Invoice.compliance_data['BR']`.
   Municipal emissores próprios are not a v1 target — after Res. CGSN
   189/2026 the Simples Nacional majority is on the Emissor Nacional.
   `GET /parametros_municipais/{codigoMunicipio}/convenio` decides at
   runtime whether a clinic is reachable this way; if not, the module
   says so and issues nothing.
4. **The clinic holds the credential; DentalPin never does** — an
   ICP-Brasil A1 e-CNPJ uploaded per clinic like verifactu's FNMT
   certificate, plus the practice's own Painel do Contribuinte
   credenciamento. No DentalPin-operated signing service, no producer
   key: the Portuguese failure mode cannot arise here.
5. **Nothing calendar-dependent is hard-coded.** ISS rates, regimes,
   deductions, retentions and cancellation/substitution windows come
   from `parametros_municipais` at runtime. CBS/IBS rates, the
   2029–2032 ISS decay and the 2033 LC 116 repeal are configuration
   with effective dates. XSD/leiaute versions, `cIndOp` and NBS
   tables and the DANFSe spec are versioned seeds replaceable without
   a code change, with homologation and production sets separable.
6. **The `IBSCBS` groups are a launch requirement, not a roadmap
   item** — destaque has been due since 01.10.2026 and NT 004 §1.1
   validates the groups fully whenever present. `br_nfse` emits them
   completely or does not emit; it never sends partial IBS/CBS data.
   Correction follows the law: immutable document, cancelamento /
   cancelamento por substituição / solicitação de análise fiscal as
   events, and **no** carta de correção.
7. **`br_tiss` is N connections, not one integration.** A
   per-operadora connection profile holds the endpoint (from that
   operadora's Portal TISS), credentials, the practice's código de
   contratado for that contract, and **the Comunicação version agreed
   with that operadora**. There is no global TISS version setting.
8. **`br_tiss` v1 covers exactly the mandatory dental processes**:
   Guia de Tratamento Odontológico (cobrança and autorização), Anexo
   de Situação Inicial via LoteAnexo, the demonstrativos de retorno,
   and Recurso de Glosa Odontológica. Elegibilidade and non-anexo
   authorisation come later and, if built, are TISS-shaped (item 41).
   **DentalPin never talks to ANS**; no code touches the 01.06.00
   monitoramento line.
9. **TUSS is seeded read-only in `br_tiss`, with vigência dates, and
   mapped to the treatment catalog by a module-owned mapping table** —
   the answer ADR 0031 gave for the BEMA. `catalog` gains no TUSS
   column. Codes validate against the **date of care**; the dental
   line is `(tabela, código, dente?, região?, faces[])` with faces
   multi-valued. **The Rol is not modelled as a coverage engine** — a
   wrong "this is covered" is worse for the practice than silence.
   No "situação final" odontogram is built as a TISS obligation;
   `br_tiss` reads the existing odontogram to fill the situação
   inicial anexo and nothing more.
10. **We do not seek SBIS S-RES certification and do not claim it.**
    The seal that mattered died in 2018; the survivor is voluntary and
    scoped to a product version and its stack. Instead the **NGS2
    requirements are adopted as an engineering target** for the
    Brazilian edition: per-entry author binding with CRO and
    timestamp, append-only notes, access control and audit, and an
    optional ICP-Brasil signing capability over a hash-chained audit
    trail as the non-ICP baseline (MP 2.200-2 art. 10 §2º). Our pages
    say "meets the NGS2 requirements", never "certified".
11. **Retention defaults to 20 years from the last entry**
    (Lei 13.787 art. 6º §5º), configurable upward, with minor-tolling
    from the patient's 18th birthday. An LGPD erasure request is
    honoured for marketing and consent-based data and **refused with a
    recorded, reasoned response for the prontuário** (art. 16, I).
    Consent is not the clinical basis (art. 11, II "f"/"a"); consent
    records are per-item, revocable and versioned, and gate images per
    CFO-196/2019 — a procedure-in-progress class that is never
    exportable, publication only of diagnosis/conclusion images by the
    treating professional, name and CRO stamped on export, no
    before/after composer. TISS payloads carry only the guia's fields,
    every disclosure is logged (art. 18, VII), and breach tooling
    targets the three-working-day deadlines.
12. **Until both modules exist, DentalPin's position in Brazil is
    "clinical record, schedule and patient invoicing; NFS-e and TISS
    pending, both feasible"** — on the Brazilian pages and in the
    readiness matrix. Unlike Germany and Portugal, this is temporary:
    nothing external blocks it.

## Consequences

### Good

- The feasibility question gating #139 closes with a sourced "yes" on
  both halves — the first market here whose answer is not "a third
  party issues, DentalPin mirrors".
- `br_nfse` gives the hook a REST/JSON reference implementation
  alongside verifactu's SOAP/mTLS; the certificate handling is an
  already-solved shape.
- Targeting SEFIN Nacional collapses what looked like 5 571
  integrations into one, and Res. CGSN 189/2026 makes that the right
  bet for our users.
- `br_tiss`'s mandatory surface is small: one guia, one anexo, two
  demonstrativos, one appeal.
- TUSS-in-module keeps `catalog` country-agnostic and reuses the
  answer already given for the BEMA, so #135 and #139 do not diverge.

### Bad / accepted trade-offs

- Both regimes are calendar-versioned and mid-reform. `br_nfse`
  tracks NT/XSD releases that moved four times in nine months;
  `br_tiss` tracks a bi-monthly cadence with a 3–12 month window.
  Someone owns that, or these rot faster than anything else here.
- `br_tiss` must speak two Comunicação versions simultaneously,
  selected per operadora. That complexity cannot be designed away.
- Onboarding is per operadora — endpoint, credentials, contract code,
  possibly the operadora's own tests (**open**).
- Adopting NGS2 without certification means we carry the requirements
  and the argument; a practice that wants a seal goes elsewhere.
- The destaque deadline has passed, so `br_nfse` v1 is larger than a
  pre-reform NFS-e module would have been.
- One `pt.json` serves Portugal and Brazil today; the issue asks for
  a separate issue with specific keys, so that stays out of scope.

## Alternatives considered

- **One `br_compliance` module.** — A practice can need the invoice
  without the convênio side; the two have different dependencies,
  cadences and owners.
- **Integrate a commercial NFS-e gateway (the ADR 0027 pattern).** —
  That pattern exists to borrow a certification we cannot hold. No
  such rule here, so a gateway buys a subscription and a dependency
  for nothing. Kept as a fallback if a clinic's municipality proves
  unreachable through SEFIN Nacional.
- **Target per-municipality web services first.** — The obvious
  reading before Res. CGSN 189/2026; now the wrong bet for the
  Simples Nacional majority, and LC 214 art. 62 is pushing the
  remaining emissores próprios into the national layout anyway.
- **Route TISS through a broker.** — Nothing in RN 501 contemplates
  one and item 134 gives the *prestador* the transport choice. A
  commercial convenience, not a standard; revisit only if
  per-operadora onboarding proves unworkable.
- **Model the Rol as a coverage engine.** — Different list from TUSS,
  and coverage is the operadora's determination.
- **Seek SBIS S-RES certification.** — Voluntary, product- and
  stack-scoped, required by nothing. Revisit if a `regulamento` under
  Lei 13.787 makes it mandatory.
- **Ship `br_nfse` without the `IBSCBS` groups.** — Destaque is
  already due and partial data is fully validated; this ships a known
  desconformidade.

## How to verify the rule still holds

- `docs/technical/country-readiness.md` and the Brazilian landing
  page state Decision 12 and never imply any Brazilian body certifies
  DentalPin.
- No module grep-matches a hard-coded ISS rate, a cancellation
  deadline in days, or a CBS/IBS percentage; each resolves through
  `parametros_municipais` or a dated configuration row.
- Backend test: a `BR` clinic issuing through `br_nfse` against a
  SEFIN Nacional stub produces a DPS that validates against the
  pinned XSD **with** `IBSCBS` populated, and is refused at issue
  time if those groups are incomplete.
- Backend test: two operadora profiles pinned to different Comunicação
  versions each produce a LoteGuias in their own namespace; a TUSS
  code whose vigência ended before the date of care is accepted, one
  that began after it is refused.
- `grep -r monitoramento backend/app/modules/br_tiss` is empty, and
  `br_tiss` contains no ANS endpoint.
- `catalog` has no TUSS, CBHPO or Rol column; the mapping lives in
  `br_tiss_*`.
- Backend test: an LGPD erasure request for a `BR` patient deletes
  marketing and consent-based records and returns a reasoned refusal
  for the prontuário; an image classified procedure-in-progress has no
  reachable export path.

## Answers to the issue

1. **National or municipal, and self-hosted software** — Context §1.
   Both paths exist; all 5 571 entes have adhered and LC 214 art. 62
   forces the national layout from 01.01.2026; Simples Nacional
   ME/EPP must use the Emissor Nacional since 01.09.2026, with API
   integration one of the two official channels. A practice may emit
   from software it developed or bought — **no certification of the
   software exists**. Decision 3.
2. **Current layout and dental fields** — Context §1–2: production
   XSD v1.01-20260209 plus the NT 004/007/008/009 `IBSCBS` groups;
   service item 4.12; `cIndOp` from Anexo VII v1.02.00. Decisions 5–6.
3. **Authentication and where the credential lives** — Context §1: an
   ICP-Brasil A1/A3 e-CNPJ held by the clinic, for mTLS and the DPS
   signature, plus self-service Painel do Contribuinte credenciamento.
   Decision 4.
4. **Cancellation and correction** — Context §1: immutable document,
   16 events, no carta de correção, correction by substitution,
   deadlines as per-municipality PAM parameters. Decision 6.
5. **TISS version and cadence** — Context §3: five separately
   versioned componentes, Comunicação 04.03.00, roughly bi-monthly
   releases, a 3–12 month implementation window, one or two live
   versions chosen bilaterally. Decision 7 answers "the part that
   will age this module fastest".
6. **Which guias, and rol ↔ catalog** — Context §3: Guia de
   Tratamento Odontológico, Anexo de Situação Inicial, demonstrativos,
   Recurso de Glosa Odontológica. TUSS (CBHPO for dentistry) is the
   coding terminology; the Rol is a coverage instrument and a
   different list. Decisions 8–9.
7. **Per operadora or standardised** — Context §3: standardised
   contract, per-operadora endpoint. Each operadora publishes its own
   address and TISS Coordinator; the shipped WSDLs carry an empty
   `<soap:address/>`. One protocol, N connections. Decision 7.

## Open questions

- Any approval step between Produção Restrita and Produção for a
  taxpayer's own NFS-e software? Nothing documented; the FAQ's
  "solicitar acesso" is municipality-scoped.
- Do municipalities running emissores próprios impose their own
  web-service credenciamento? Outside the national rule.
- Do individual operadoras homologate a prestador's software before
  opening their webservice? ANS neither mandates nor forbids it.
- May a dental consultation be billed on the Guia de Consulta?
- Has any `regulamento` under Lei 13.787/2018 ever been issued? None
  found — which is what leaves S-RES certification voluntary.
- Verbatim text of RN 501/2022 and IN ANS 9/2022 (hosts unreachable;
  operative content taken from ANS's own documentation, which tags
  each rule with its source).
- Whether ANPD's planned health-data guia orientativo narrows
  art. 11 §4º in a way that touches TISS payload scope.

## Readiness matrix row

| Brazil | ✅ `pt` (pt-BR wording tracked separately) | ✅ | ❌ NFS-e: feasible, no software certification exists — the practice emits from its own software with an ICP-Brasil e-CNPJ (Res. CGNFS-e 3/2023 art. 3º § único); `br_nfse` pending, targeting the SEFIN Nacional API with the `IBSCBS` groups (ADR 0034) | ❌ TISS: feasible — "qualquer solução tecnológica poderá ser utilizada" (RN 501/2022, CO item 139); `br_tiss` pending, one protocol and N per-operadora connections, Comunicação 04.03.00; DentalPin never talks to ANS (ADR 0034) | #139 (answered) |

## References

- Issue #139; `backend/app/modules/verifactu/` and
  `docs/modules/verifactu.md`;
  `backend/app/modules/billing/hooks.py`; ADR 0027 (Portugal — the
  certification question answered the other way), ADR 0028 (France),
  ADR 0031 (Germany — the catalog-in-module precedent), ADR 0002
  (per-module Alembic branches)
- `adr-br/SOURCES.md` — every URL with the sentence it supports,
  fetched 2026-09-12
- CF art. 156: <https://www.planalto.gov.br/ccivil_03/constituicao/constituicao.htm>;
  LC 116/2003: <https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm>;
  LC 214/2025: <https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp214.htm>
- Resolução CGNFS-e nº 3/2023: <https://www.gov.br/nfse/pt-br/biblioteca/portarias-e-resolucoes-cgnfs-e/resolucaocgnfsen330082023.pdf>;
  nº 1/2023: <https://www.gov.br/nfse/pt-br/biblioteca/portarias-e-resolucoes-cgnfs-e/resolucaocgnfsen116032023.pdf>
- NFS-e documentação técnica: <https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual>;
  RTC notes: <https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc>;
  NT 004 v2.0: <https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/rtc-producao-restrita-piloto/nt-004-se-cgnfse-novo-layout-rtc-v2-00-20251210.pdf>;
  Manual dos Contribuintes v1.2: <https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/documentacao-atual/manual-contribuintes-emissor-publico-api-sistema-nacional-nfs-e-v1-2-out2025.pdf>;
  Manual Integrado SN NFS-e: <https://www.gov.br/nfse/pt-br/biblioteca/documentacao-tecnica/leiaute-e-esquemas-antigos/manualintegradosnnfse_v1-00-02-producao.pdf>
- Res. CGSN 189/2026 (Emissor Nacional): <https://www.gov.br/nfse/pt-br/noticias/nfs-e-e-simples-nacional-obrigatoriedade-de-emissao-atraves-do-emissor-nacional>;
  IBS/CBS destaque (Ato Conjunto RFB/CGIBS 4/2026): <https://www.gov.br/nfse/pt-br/noticias/cgnfs-e-orienta-sobre-os-prazos-para%20destaque-de-ibs-cbs-nas-notas-fiscais-de-servico>;
  RFB Orientações 2026: <https://www.gov.br/receitafederal/pt-br/acesso-a-informacao/acoes-e-programas/programas-e-atividades/reforma-tributaria-do-consumo/orientacoes-2026>
- Padrão TISS: <https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss>;
  Componente Organizacional 202607, Conteúdo e Estrutura 202511 and
  Comunicação (XSD/WSDL) — exact URLs in `SOURCES.md` §11;
  histórico de versões: <https://www.gov.br/ans/pt-br/assuntos/prestadores/padrao-para-troca-de-informacao-de-saude-suplementar-2013-tiss/padrao-tiss-historico-das-versoes-dos-componentes-do-padrao-tiss>;
  Rol: <https://www.gov.br/ans/pt-br/acesso-a-informacao/participacao-da-sociedade/atualizacao-do-rol-de-procedimentos>
- CEO (Res. CFO-118/2012): <https://website.cfo.org.br/wp-content/uploads/2018/03/codigo_etica.pdf>;
  Res. CFO-91/2009: <https://sistemas.cfo.org.br/visualizar/atos/RESOLU%C3%87%C3%83O/SEC/2009/91>;
  Res. CFO-196/2019: <https://sistemas.cfo.org.br/visualizar/atos/RESOLU%C3%87%C3%83O/SEC/2019/196>;
  Res. CFO-278/2025: <https://sistemas.cfo.org.br/visualizar/atos/RESOLU%C3%87%C3%83O/SEC/2025/278>;
  CFO Manual do Prontuário (2026): <https://website.cfo.org.br/wp-content/uploads/2026/03/CFO_Manual_do_Prontuario_Ebook.pdf>
- Res. CFM 1.821/2007: <https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2007/1821_2007.pdf>;
  Res. CFM 2.218/2018 (revokes the seal): <https://sistemas.cfm.org.br/normas/arquivos/resolucoes/BR/2018/2218_2018.pdf>;
  SBIS Manual S-RES v5.0: <https://www.sbis.org.br/certificacao/Manual_Certificacao_S-RES_SBIS_v5-0.pdf>
- Lei 13.787/2018: <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13787.htm>;
  MP 2.200-2/2001: <https://www.planalto.gov.br/ccivil_03/mpv/antigas_2001/2200-2.htm>;
  LGPD: <https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm>;
  Res. CD/ANPD nº 15/2024: <https://www.in.gov.br/web/dou/-/resolucao-cd/anpd-n-15-de-24-de-abril-de-2024-556243024>
