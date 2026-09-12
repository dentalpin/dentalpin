# 0035 — United States: licensing, not certification, decides the dental claims position (CDT / X12 837D / HIPAA)

- **Status:** proposed
- **Date:** 2026-09-12
- **Deciders:** maintainers
- **Tags:** compliance, billing, privacy, united-states

## Context

Issue #137 asks five things before any code: what CDT is and whether an
open-source project may ship it, which X12 transactions are needed on
day one, how a self-hosted practice reaches payers, how radiographs
travel with a claim, and what the software owes a HIPAA covered entity.
Sources are the primary texts: 45 CFR Parts 160/162/164/171 and 42 CFR
414.1305 (eCFR versioner API, Title 45 current 2026-09-10), 16 CFR 318,
21 CFR 1300/1311, Federal Register 90 FR 898, 91 FR 14350, 85 FR 84472
and 89 FR 97710, the CMS Administrative Simplification and EPCS pages,
healthit.gov, and the licensing pages of the two copyright holders —
X12 and the ADA. Every quote below is in `SOURCES.md` with its URL.
Anything unconfirmed from an official source is marked **open**.

The headline is that the United States is the opposite of Portugal
(ADR 0027), France (ADR 0028) and Germany (ADR 0031). **No US regulator
approves, certifies or registers dental practice management software.**
What blocks us instead is intellectual property: the code set and the
transaction guide a claim needs are both privately owned, and neither
may be redistributed.

### 1. The transactions

Adopted under HIPAA Administrative Simplification, 45 CFR Part 162,
each incorporated by reference through § 162.920:

| Transaction | Section | Adopted document |
|---|---|---|
| Dental claim 837D | 162.1102(b)(2)(ii) | "Health Care Claim: Dental (837), May 2006, ASC X12N/005010X224" + Type 1 Errata 005010X224A1 |
| Eligibility 270/271 | 162.1202(b)(2)(ii) | ASC X12N/005010X279 |
| Claim status 276/277 | **162.1402**(b)(2) | ASC X12N/005010X212 + E1 |
| Remittance 835 | 162.1602(d)(2) | ASC X12N/005010X221 |
| Prior auth 278 | 162.1302(b)(2)(ii) | ASC X12N/005010X217 + E1 |

**Nothing newer than 5010 is adopted.** CMS: "ASC X12 Version 5010 is
the adopted standard format for transactions, except those with retail
pharmacies." A Federal Register full-text query returns zero documents
for "007030", "X12 version 7030" and "8010 HIPAA standard". § 162.1102
was restructured in 2025 — (c) now runs "through August 14, 2027" and
the new (e)(2)(ii)/(f) re-adopt the *identical* dental TR3 "on and
after April 14, 2028". One trap: "005010X224**A2**", cited by CMS's own
Medicare companion guide and every state Medicaid guide, appears
nowhere in Part 162 — its regulatory standing is **open**.

**Who must comply:** § 160.102(a)(3), "A health care provider who
transmits any health information in electronic form in connection with
a transaction covered by this subchapter"; CMS lists "Dentists".
§ 162.923(a) requires the standard only when transacting "with another
covered entity"; (b) exempts a plan's direct-data-entry portal from the
*format* but not the *content*.

**The route.** A clearinghouse is permitted, never required —
§ 162.923(c): a covered entity "may use a business associate, including
a health care clearinghouse". Decisively, § 162.930(b) lets it "Receive
a nonstandard transaction (for example, nonstandard format and/or
nonstandard data content) from the covered entity and translate it into
a standard transaction for transmission on behalf of the covered
entity" — that is the definition of the thing (§ 160.103). Enrolment
binds the *practice*: CMS's EDI agreement "must be executed by each
provider … either directly with Medicare or through a billing service
or clearinghouse". No step approves software.

**Identifiers.** NPI, "a 10-position numeric identifier, with a check
digit in the 10th position" (§ 162.406), used "on all standard
transactions" (§ 162.410(a)(2)). Provider taxonomy is an external code
set "self-selected by the provider" that NUCC licenses to vendors;
whether it is *required* on the 837D is **open** (it lives inside the
paywalled TR3).

**Attachments.** Final rule CMS-0053-F, 91 FR 14350 (24 March 2026),
adopts X12N 275 (006020X314), X12N 277 (006020X313) and the March 2022
HL7 Attachments IG, "effective on May 26, 2026" with compliance "24
months from the effective date" — **26 May 2028**. Prior-authorization
attachments were dropped from the final rule.

### 2. The licensing — the decisive finding

**CDT.** § 162.1002(a)(4) adopts the "Code on Dental Procedures and
Nomenclature, as maintained and distributed by the American Dental
Association, for dental services", naming no edition; § 162.1000(a)
requires the one "valid at the time the health care is furnished". The
ADA: "The ADA is the exclusive copyright owner of CDT … all use,
copying or distribution of CDT, or any portion thereof … in any product
or services …, whether in printed, electronic or other format, requires
a valid commercial user license from the ADA." And: "With commercial
use, you must bundle the Codes with other assets in your product or
service and redistribution of the CDT Codes alone is not permitted."
The bundling clause catches exactly what a PMS does — "access, use,
extraction, interpretation or manipulation of the Codes … to produce or
enable output … that could not be created without the CDT Codes
embedded in the product/service **even if the CDT Codes may not be
visible or directly accessible**". A seed migration, a validation list
or a test fixture is inside it.

The escape hatch is the practice, not the vendor: "Dentists, dental
teams and hospitals do not need a license to use CDT", and buying the
manual "includes the right to use the code in a practice and use CDT
within practice management software."

**X12.** The regulation itself says the guide is sold, not published:
§ 162.920 makes the TR3s available "for inspection at" CMS and NARA and
obtainable only "from … ASC X12"; the 2024 CFR edition adds "A fee is
charged for all implementation specifications, including Technical
Reports Type 3." X12's policy: "Direct distribution of X12's
copyrighted products by any organization or individual to another
organization or individual is strictly prohibited"; "No organization
may post X12 Standards, Technical Reports … on its website for public
reference at any time". You may not even hand a TR3 to a trading
partner — "Each organization needs to hold their own active license".

Then the clause that settles this ADR. X12's licence agreements
(Licensor X12, Publisher Washington Publishing Company), § 2.1:

> "For avoidance of doubt, the foregoing restrictions include that
> Licensee shall not license, or permit to be licensed, under the terms
> of an Open Source License the Licensee Software or Combined Software
> Solutions, and Licensee shall not use, or permit others to use, the
> Licensed Content in any manner that would require the distribution or
> licensing of any Licensed Content pursuant to, or otherwise subject
> it to the terms of, an Open Source License."

"Open Source License" is defined to include "the Apache License", "the
Berkeley Software Distribution (BSD)", the MPL, the GPL family and "any
licenses that are defined as OSI (Open Source Initiative) licenses as
listed on the site www.opensource.org". "Licensed Content" reaches the
guides: the definitions name "derivatives (such as technical reports)",
"X12 TR3 Table Data" and "Implementation Guides". The cheap Developer
licence is production-prohibited; shipping X12 IP inside software is
the "Commercial Use Partner" tier, priced per agreement.

This is not "we cannot ship a PDF". DentalPin is BSL 1.1 and every
release converts to **Apache 2.0 after four years** (ADR 0004) — a
licence X12 names. An encoder built under an X12 licence would collide
with our own licence trajectory on a four-year timer. Where the line
falls between *Licensed Content* and an independently written encoder
conforming to a federally mandated wire format is exactly the argument;
X12 has published no position — **open**, a question for counsel.

### 3. Certification — there isn't one

The ASTP/ONC Health IT Certification Program "is a voluntary
certification program". CEHRT is required only by the Promoting
Interoperability programmes and the MIPS PI category. The exclusion of
dentistry is **not** that dentists fall outside the eligible-clinician
definition — CMS says the opposite: "dentists are included in the
statutory definition of physician at section 1861(r)(2) of the Act and
would generally be considered and treated as a physician for purposes
of enrollment, compliance, and other administrative programs" (89 FR
97710). The exclusion is arithmetic: routine dental care is an excluded
Medicare benefit (42 CFR 411.15(i)), so a dental practice has
essentially no Part B volume and never clears the low-volume threshold
— "allowed charges … less than or equal to $90,000, … 200 or fewer
Medicare Part B-enrolled individuals, or … 200 or fewer covered
professional services" (42 CFR 414.1305, 414.1310(b)(1)(iii)).
**Nothing requires a dental practice to use certified health IT.**

Information blocking (45 CFR Part 171) binds "actors": a provider, a
"health IT developer of certified health IT", a health information
network. The developer prong requires "one or more Health IT Modules
certified under a program for the voluntary certification of health
information technology" — an uncertified product is not an actor. The
**practice** is an actor as a provider, which is a reason to make
export easy, not to certify. TEFCA is a framework "by which HINs
voluntarily elect to abide".

### 4. HIPAA

**Where the BAA line falls.** § 160.103 makes someone a business
associate only if they, "On behalf of such covered entity … create[],
receive[], maintain[], or transmit[] protected health information", or
provide a service "where the provision of the service involves the
disclosure of protected health information … to the person". HHS FAQ
3013: "HIPAA does not require a covered entity or its business
associate (e.g., EHR system developer) to enter into a business
associate agreement with an app developer that does not create,
receive, maintain, or transmit ePHI on behalf of or for the benefit of
the covered entity". A project that only distributes software a
practice installs and runs itself is therefore **not** a business
associate. What flips it, all sourced: DentalPin-operated hosting ("An
entity that maintains ePHI on behalf of a covered entity … is a
business associate, even if the entity cannot actually view the ePHI",
and "even if it does not hold a decryption key"); paid remote support
("IT contractor or vendor (e.g., EHR vendor, Managed Services Provider)
that provides maintenance and/or support services … that require the
contractor or vendor to create, receive, maintain, or transmit ePHI");
any project-run backup, telemetry or AI service. The conduit exception
is "limited to transmission-only services" and would not save a hosted
offer.

**Security Rule, 45 CFR 164.312**, unchanged since 2013. Measured
against the tree today:

| Requirement | Status |
|---|---|
| (a)(2)(i) Unique user identification (**Required**) | met — per-user accounts, clinic-aware RBAC (ADR 0024) |
| (d) Person or entity authentication (bare standard) | met — httpOnly cookie auth, refresh rotation (ADR 0023) |
| (b) Audit controls (**bare standard, no "addressable" escape**) | **gap** — `activity_journal` is append-only but subscribes to published *write* events only; the one view event in the tree is `budget.viewed` on a public quote link. Who *read* a chart is not recorded |
| (a)(2)(ii) Emergency access procedure (**Required**) | **gap** — no break-glass path |
| (a)(2)(iii) Automatic logoff (Addressable) | **gap** — no idle timeout |
| (a)(2)(iv) / (e)(2)(ii) Encryption (Addressable) | operator duty (`compliance-posture.md` §6) |
| (c) Integrity / (e)(1) Transmission security | partly — immutable journal, soft deletes; TLS is the operator's |

"Addressable" is not optional: § 164.306(d)(3) requires assessing it
and, if not implemented, documenting why "and implement an equivalent
alternative measure if reasonable and appropriate". § 164.306(b) scales
the answer to "The size, complexity, and capabilities of the covered
entity".

**Privacy Rule.** Minimum necessary (§ 164.502(b)) is implemented as
role-based access — § 164.514(d)(2) asks the entity to identify "Those
persons or classes of persons … who need access to protected health
information to carry out their duties" and the categories each needs,
which `clinic_role_overrides` already models; treatment is exempt
(§ 164.502(b)(2)(i)). Right of access (§ 164.524): act "no later than
30 days after receipt", one extension of "no more than 30 days", and
for electronic records "in the electronic form and format requested by
the individual, if it is readily producible".

**Breach Notification.** § 164.402 presumes a breach unless a
four-factor assessment shows low probability of compromise — one factor
is "Whether the protected health information was actually acquired or
viewed", unanswerable without the read log above. § 164.404(b):
individuals "in no case later than 60 calendar days after discovery".
§ 164.408: 500+ contemporaneously to HHS, under 500 in an annual log
filed within 60 days of year end. The FTC rule does not reach us —
16 CFR 318.1(a): "This part does not apply to HIPAA-covered entities,
or to any other entity to the extent that it engages in activities as a
business associate of a HIPAA-covered entity."

**The proposed Security Rule.** 90 FR 898 (6 January 2025), RIN
0945-AA22; comments closed 7 March 2025; **no final rule as of
2026-09-12** (a Federal Register API query on the RIN returns exactly
one document; the expected date is **open**). It would "remove the
distinction between required and addressable implementation
specifications and make all implementation specifications required",
require encryption of "all ePHI at rest and in transit", mandate MFA at
proposed § 164.312(f)(2)(ii), and add an asset inventory, network map,
network segmentation and an annual compliance audit. If finalised:
effective 60 days after publication, compliance 180 days later. Note
what that does to ADR 0022 — TOTP is *deferred*, and this NPRM is the
trigger to un-defer it.

### 5. E-prescribing

Dentists are in scope: 21 CFR 1300.01 defines an individual practitioner
as "a physician, dentist, veterinarian, or other individual licensed …
to dispense a controlled substance". EPCS needs two of three
authentication factors with a hard token meeting "at least the criteria
of FIPS 140-2 Security Level 1" (§ 1311.115), DEA identity proofing,
and — the blocker — a third-party audit under § 1311.300 by "a person
qualified to conduct a SysTrust, WebTrust, or SAS 70 audit" or a
Certified Information System Auditor, or certification by a
DEA-approved body, redone "Whenever a functionality related to
controlled substance prescription requirements is altered or every two
years, whichever occurs first". That is a per-version audit of an
unmodifiable application — the Portugal problem (ADR 0027) in US dress.
Separately, SUPPORT Act § 2003 "generally mandates that the prescribing
of a Schedule II, III, IV, or V controlled substance under Medicare
Part D be done electronically … beginning January 1, 2021" (85 FR
84472), compliance actions "no earlier than January 1, 2023" (86 FR
64996); threshold 70 %, the action a notice, and CMS "automatically
provides" an exception to prescribers issuing "100 or fewer qualifying
Medicare Part D controlled substance prescriptions in the measurement
year" — every ordinary dental practice. Some states go further: New
York has required electronic prescribing of controlled *and*
non-controlled substances by all practitioners except veterinarians
since 27 March 2016.

## Decision

1. **DentalPin ships no CDT content — none, anywhere.** No code
   numbers, no nomenclature, no descriptors, in the repo, in seeds, in
   fixtures, in tests or in documentation examples. The ADA's bundling
   clause reaches invisible use, so "just the numbers in a migration"
   is not a loophole.
2. **The practice supplies its own CDT.** A US clinic holds its own
   licence by buying the CDT manual, which "includes the right to use
   the code in a practice and use CDT within practice management
   software". `us_claims` provides an **importer** (paste or CSV) that
   loads the clinic's list into clinic-scoped rows, plus a mapping from
   `treatment_catalog_items` to the code the clinic entered. Clinic
   data, never repo data.
3. **This answers #137's catalog question differently from #135.** The
   US needs no country-supplied treatment catalog — it needs one
   nullable, country-module-owned *code mapping* per catalog item.
   `catalog` keeps `internal_code` and learns nothing about the US.
4. **DentalPin does not write an X12 encoder and does not take an X12
   licence.** § 2.1 forbids licensing the resulting software under an
   Open Source License, which names Apache 2.0 — the licence every
   release converts to four years after release (ADR 0004). Building
   the encoder means breaching that clause or abandoning the
   conversion.
5. **Claims leave DentalPin as a documented non-standard JSON payload
   to a clearinghouse acting as the practice's business associate.**
   § 162.930(b) authorises exactly this; the clearinghouse holds the
   X12 licence, produces the 837D and is the covered entity's agent.
   DentalPin stores the acknowledgement, status and remittance as a
   mirror — the same "third party issues, DentalPin mirrors" pattern
   as ADRs 0027 and 0028.
6. **Module `us_claims`**, `US`-gated, `auto_install=False`, registered
   through `BillingHookRegistry` in the `verifactu` shape: own
   `us_claims_*` tables, own Alembic branch, own Nuxt layer, uninstall
   leaves nothing behind. Day one is the claim draft plus eligibility
   (270/271) and remittance (835) posting, all through the
   clearinghouse's REST API — **no X12 on the wire from DentalPin,
   ever**. `billing` learns nothing about the US.
7. **Attachments stay where they are.** Radiographs live in `media` /
   `documents`; `us_claims` sends a reference and lets the
   clearinghouse produce the 275. Compliance date 26 May 2028.
8. **No certification is sought, because none exists.** DentalPin does
   not apply for ASTP/ONC certification, does not become a "health IT
   developer of certified health IT", and does not join TEFCA. Recorded
   so it is not re-litigated every time a US prospect asks "are you ONC
   certified?" — the answer is "no dental PMS is, and nothing requires
   it".
9. **The HIPAA posture is written down as a split, and the gaps close
   before the US is called ready.** Self-hosted: DentalPin is not a
   business associate and signs no BAA. DentalPin-operated SaaS:
   business associate, signs a BAA, and the § 164.504(e)(2) terms
   become contractual. Three code items ship before any US readiness
   claim: a **PHI read-access log** (§ 164.312(b), a bare standard we
   currently fail), an **automatic logoff**, and an **emergency access
   path**. `gdpr`'s DSR tracker, export endpoint and breach register
   are generalised to serve § 164.524 and §§ 164.404–410 rather than
   duplicated.
10. **E-prescribing is out of scope and stays out.** EPCS needs a
    per-version third-party audit of an application the practice may
    not modify. A US edition integrates a certified e-prescribing
    gateway or does not prescribe controlled substances at all.
11. **Until `us_claims` exists, DentalPin's position in the US is
    "clinical record, schedule and patient invoicing; claims with your
    existing system"**, on the US pages and in the readiness matrix.
    Unlike Portugal and Germany this is a build backlog, not a legal
    wall — nothing stops us but work and a clearinghouse contract.

## Consequences

### Good

- The question #137 called decisive gets a sourced answer, and it is
  the answer that reshapes the design: ship no code set, ship no
  encoder, drive a clearinghouse.
- The US is the cheapest major market to enter — no certification, no
  homologation, no registered producer, no per-version filing. The
  contrast with ADRs 0027/0028/0031 is worth saying on the site.
- The clearinghouse route removes the X12 licence problem rather than
  managing it, and keeps BSL's Apache conversion intact.
- The HIPAA gap list is short, concrete and useful everywhere: a read
  log, an idle timeout and a break-glass path improve every market.

### Bad / accepted trade-offs

- A US practice cannot bill from DentalPin until the connector ships,
  and then needs a clearinghouse account and a per-claim or monthly fee.
- We depend on a commercial clearinghouse's API and uptime; a change of
  provider is a new driver.
- The CDT import is friction the incumbents do not have — they hold an
  ADA licence and ship the codes. Onboarding must make the import a
  two-minute step and the annual edition change a prompt.
- No ONC certification means no CEHRT story if a corporate DSO or a
  Medicaid programme ever asks for one.

## Alternatives considered

- **Take an ADA licence and ship CDT.** — Royalty-bearing per-product
  agreement; the ADA publishes no terms for a free, source-available
  distribution anyone may fork, and the licence would not travel with a
  fork. Rejected; kept as a question to the ADA.
- **Take an X12 Commercial Use Partner licence and write the 837D.** —
  § 2.1 forbids licensing the combined software under an Open Source
  License and ADR 0004 converts every release to Apache 2.0. Rejected
  on the licence collision, not the effort.
- **Clean-room 837D encoder from public companion guides.** — Those are
  published "to be used in conjunction with, and not in place of, the
  X12 … TR3s"; they do not carry the requirements, and X12 forbids
  artifacts that "Replicate the information presented in the associated
  TR3". Residual legal risk unquantified, and it would sit on every
  self-hoster.
- **Direct payer connections, no clearinghouse.** — Lawful
  (§ 162.923(c) says "may"), but needs the 837D we just declined to
  write, plus per-payer enrolment and testing.
- **Each plan's direct data entry portal.** — § 162.923(b) allows it
  and needs no standard format, but it is manual per claim; it is the
  status quo the issue calls "not a product anyone switches to".
- **Claim HIPAA compliance now, fix the gaps later.** — Audit controls
  is a bare standard, not an addressable one. Claiming it while chart
  reads go unlogged is what `compliance-posture.md` §7 exists to stop.

## How to verify the rule still holds

- `grep -rE '\bD[0-9]{4}\b' backend/ frontend/ docs/` returns nothing:
  no CDT code ever enters the repo. Worth a `docs-layout`-style CI job.
- No module emits an X12 envelope: grep for `ISA*`, `GS*`, `ST*837` and
  `005010X224` returns nothing, and `us_claims` has no EDI serialiser.
- `docs/technical/country-readiness.md` and the US landing page say
  "claims through a clearinghouse; you supply your CDT licence", and no
  page claims ONC certification or HIPAA compliance.
- Backend test: a `US` clinic invoice whose catalog item has no
  clinic-supplied procedure code is refused at claim-draft time with
  the CDT-licence message.
- Backend test: reading a patient chart writes an access-log row that
  survives the read transaction and cannot be edited.
- `compliance-posture.md` §7 keeps "HIPAA certification" in the *not
  claimed* list while Decision 9's three items are open.

## Answers to the issue

1. **The code set.** CDT is the adopted HIPAA dental code set
   (§ 162.1002(a)(4)), owned by the ADA, and **may not be distributed
   with the software**: product use "requires a valid commercial user
   license" and "redistribution of the CDT Codes alone is not
   permitted". The practice must hold its own licence — which it
   already does the moment it buys the CDT manual. For the catalog: a
   nullable code-mapping field owned by `us_claims`, not a US catalog.
2. **The transactions.** Day one is 837D plus 270/271, as the issue
   guessed; 835 follows immediately because posting remittances by hand
   is the pain the connector removes; 276/277 and 278 later. All 5010,
   nothing newer adopted (Context §1).
3. **The route.** Enrolment is per practice, not per software, and no
   step approves the program. Self-hosting is fully compatible. A
   clearinghouse is optional in law but is the only route that avoids
   the X12 licence, and § 162.930(b) expressly lets it take our
   non-standard payload.
4. **Attachments.** Until now, payer portals and paper. From 26 May
   2028 the standard is X12N 275 (006020X314) with the HL7 Attachments
   IG (CMS-0053-F). Same answer as claims: we store the image, the
   clearinghouse produces the transaction.
5. **HIPAA posture.** Context §4 and Decision 9. We have: RBAC as the
   minimum-necessary mechanism, an append-only journal, soft deletes, a
   DSR tracker, a breach register. We lack, named honestly: a PHI read
   log (a **required** standard), automatic logoff, emergency access,
   and MFA — deferred in ADR 0022 and proposed to become mandatory by
   90 FR 898. BAA boundary: nobody hosting means nobody is a business
   associate (HHS FAQ 3013); the hosted offer is one and signs a BAA.

## Open questions

- Whether the ADA will license CDT to a free, source-available project
  at all — every published licence type presupposes a commercial
  product with royalties. Ask in writing; Decision 2 stands either way.
- Where X12 draws the line between *Licensed Content* and an
  independently written encoder conforming to a mandated format. No
  published position. Counsel's question, not ours.
- The regulatory standing of errata 005010X224A2, which every payer
  cites and Part 162 does not contain.
- Whether provider taxonomy is required or situational on the 837D
  (answerable only from the paywalled TR3, or from a clearinghouse).
- Whether any 45 CFR 170.315 criterion is dental-specific — not
  established; the practical answer does not depend on it.
- The residual information-blocking exposure: the "health information
  network or health information exchange" prong of § 171.102 is keyed
  to controlling exchange "Among more than two unaffiliated individuals
  or entities", not to holding a certified module. A future
  DentalPin-operated exchange between clinics needs re-reading.
- Which clearinghouses expose a REST API to a self-hosted customer, at
  what price, and whether any will contract with a practice rather than
  a software vendor. Maintainer task before any code.

## Readiness matrix row

| United States | ✅ `en` | ✅ | ✅ patient invoicing works as-is | ❌ Claims: no US regulator certifies dental PMS — the blocker is IP, not approval. DentalPin ships no CDT (ADA commercial licence; the practice supplies its own) and writes no X12 837D (X12's licence forbids Open Source licensing of the combined software, and ADR 0004 converts to Apache 2.0); `us_claims` sends a non-standard payload to a clearinghouse acting as the practice's business associate (45 CFR 162.930(b); ADR 0035). HIPAA: self-hosted means DentalPin is no business associate and signs no BAA; the hosted offer is one and does. Read-access logging, automatic logoff and emergency access are open before any readiness claim | #137 |

## References

- Issue #137; `backend/app/modules/billing/hooks.py`;
  `backend/app/modules/verifactu/`; `catalog/models.py:143`;
  `docs/technical/compliance-posture.md`;
  `docs/technical/activity_journal/overview.md`; ADRs 0004, 0022, 0023,
  0024, 0027, 0028, 0031
- **`SOURCES.md` carries every verbatim quote with its URL and fetch
  date; the list below is the shortest path back to each text.**
- 45 CFR 160/162/164/171 and 16 CFR 318 on the eCFR, e.g.
  <https://www.ecfr.gov/current/title-45/section-162.1102>,
  `…/section-162.920`, `…/section-162.923`, `…/section-162.930`,
  `…/section-162.1002`, `…/section-160.103`, `…/section-164.312`,
  `…/section-164.306`, `…/section-164.524`, `…/section-171.102`,
  <https://www.ecfr.gov/current/title-16/section-318.1>
- HHS business associates FAQ 3013, the "Business Associates" guidance
  page and the cloud-computing guidance:
  <https://www.hhs.gov/hipaa/for-professionals/faq/3013/does-hipaa-require-a-covered-entity-to-enter-into-a-business-associate-agreement.html>
- Security Rule NPRM, 90 FR 898: <https://www.federalregister.gov/documents/2025/01/06/2024-30983/hipaa-security-rule-to-strengthen-the-cybersecurity-of-electronic-protected-health-information>;
  attachments final rule CMS-0053-F: <https://www.cms.gov/newsroom/fact-sheets/administrative-simplification-adoption-standards-health-care-claims-attachments-transactions>
- CMS Administrative Simplification (adopted standards, covered
  entities, EDI enrolment) and the EPCS programme page:
  <https://www.cms.gov/priorities/key-initiatives/burden-reduction/administrative-simplification/hipaa/adopted-standards-operating-rules>
- X12: <https://x12.org/products/ip-use>,
  <https://ecommerce.x12.org/terms-policies-licenses>,
  <https://x12.org/products/licensing-program>
- ADA: <https://www.ada.org/publications/ada-store-products/licensing-for-commercial-users>
- healthit.gov certification programme overview; 42 CFR 414.1305;
  21 CFR 1300.01, 1311.115, 1311.300; NY DOH e-prescribing
