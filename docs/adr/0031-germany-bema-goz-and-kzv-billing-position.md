# 0031 — Germany: KZBV suitability finding decides the billing position for DE clinics (BEMA / GOZ / KZV)

- **Status:** proposed
- **Date:** 2026-09-10
- **Deciders:** maintainers
- **Tags:** compliance, billing, germany, positioning

## Context

Issue #135 asks four things before any code: how the BEMA and GOZ
catalogs are built, what the KZV submission is and whether a
self-hosted installation can produce it, whether software needs formal
approval before a practice may bill with it, and what GOZ billing needs
beyond `billing`. Sources read are the primary texts: the
Bundesmantelvertrag-Zahnärzte (BMV-Z, Gesamtausgabe 01.07.2025) with
Anlagen 1, 8a and 15, the BEMA (Anlage A, Stand 01.01.2026), the GOZ
as published on gesetze-im-internet.de, § 55 SGB V, § 4 UStG, the KZBV
pages on Programmmodule, Herstellerliste, papierlose Abrechnung, EBZ
and Festzuschüsse, one KZV's Abrechnung pages (KZVB) and the BMF
e-invoicing FAQ. Points not confirmed from those are marked **open**.

### 1. The catalogs

**BEMA.** "Einheitlicher Bewertungsmaßstab für zahnärztliche
Leistungen gemäß § 87 Abs. 2 und 2h SGB V", Anlage A to the BMV-Z,
set by the Bewertungsausschuss of KZBV and GKV-Spitzenverband (last
change: Beschluss of 12.12.2025, in force 01.01.2026). Allgemeine
Bestimmung 1: it "bestimmt den Inhalt der abrechnungsfähigen
zahnärztlichen Leistungen und ihr wertmäßiges, in Punkten
ausgedrücktes Verhältnis zueinander". Five parts: Teil 1
konservierende und chirurgische Leistungen und Röntgenleistungen;
Teil 2 Kieferbruch, Kiefergelenkserkrankungen, obstruktive
Schlafapnoe; Teil 3 Kieferorthopädie; Teil 4 systematische
Parodontitis-Behandlung; Teil 5 Zahnersatz und Zahnkronen. Each
position carries a Punktzahl ("zum Beispiel 32 für eine einflächige
Füllung im Frontzahnbereich"); the price is Punktzahl × Punktwert,
and "der Punktwert wird auf Ebene der Länder zwischen den
Kassenzahnärztlichen Vereinigungen (KZVen) und den Krankenkassen
jährlich neu verhandelt", except Teil 5, which has a federal Punktwert
negotiated by KZBV and GKV-SV. Allg. Best. 3: services missing from
the BEMA are valued through the GOÄ at 9 GOÄ points = 1 BEMA point.
Allg. Best. 5: material, lab and postage costs are outside the point
values. Anlage 1 BMV-Z Nr. 2.1: the Behandlungsfall for Teil 1 is the
whole treatment by the same dentist within one Kalendervierteljahr;
Nr. 2.4: every service carries its Behandlungstag and the tooth in the
two-digit FDI scheme.

**GOZ.** Gebührenordnung für Zahnärzte of 22.10.1987, last amended by
the Verordnung of 05.12.2011 (the "GOZ 2012"), a federal regulation
published by the BMJ. § 5 (1): "Die Höhe der einzelnen Gebühr bemißt
sich nach dem Einfachen bis Dreieinhalbfachen des Gebührensatzes.
Gebührensatz ist der Betrag, der sich ergibt, wenn die Punktzahl der
einzelnen Leistung des Gebührenverzeichnisses mit dem Punktwert
vervielfacht wird. Der Punktwert beträgt 5,62421 Cent." Rounding to
the cent only after multiplying by the Steigerungsfaktor. § 5 (2):
"Der 2,3fache Gebührensatz bildet die nach Schwierigkeit und
Zeitaufwand durchschnittliche Leistung ab; ein Überschreiten dieses
Gebührensatzes ist nur zulässig, wenn Besonderheiten der […]
Bemessungskriterien dies rechtfertigen". § 2 (1)–(2): a higher fee may
be agreed in writing, per case, before treatment, listing Nummer,
Bezeichnung, Steigerungssatz and Betrag plus the note that
reimbursement may be incomplete; Punktzahl and Punktwert cannot be
varied. § 2 (3): Verlangensleistungen (§ 1 (2) S. 2) "müssen in einem
Heil- und Kostenplan schriftlich vereinbart werden" before treatment,
marked as such. § 6 (1): Analogleistungen "entsprechend einer nach
Art, Kosten- und Zeitaufwand gleichwertigen Leistung"; § 6 (2): the
GOÄ sections a dentist may bill (B I–VI, C, E V/VI, J, L, M, N 4852,
O). § 9: lab work is passed through as Auslagen at actual cost; a
Kostenvoranschlag must be offered when lab costs will exceed 1 000 €,
and the patient informed at once if they will overrun by more than
15 %. Nr. 1040 "Professionelle Zahnreinigung", 28 points, is a GOZ
position — PZR is private for everyone.

**Festzuschüsse (Zahnersatz).** § 55 (1) SGB V: befundbezogene
Festzuschüsse of "60 Prozent der […] festgesetzten Beträge" for the
Regelversorgung, rising to 70 % with five and 75 % with ten
uninterrupted bonus years; § 55 (2): Härtefall adds up to 40 % capped
at actual cost. KZBV: the system exists since 2005, the practice
"verpflichtet, vor jeder anstehenden Zahnersatzbehandlung die
jeweiligen Festzuschussbefunde zu ermitteln und im Heil- und
Kostenplan einzutragen"; about 50 Befunde whose amounts the G-BA
adjusts yearly (next: 01.01.2026). "Seit 1. Januar 2023 wird der
Heil- und Kostenplan […] in der Zahnarztpraxis elektronisch erstellt
und der Krankenkasse übermittelt"; the approval comes back
electronically; the patient receives "eine Rechnung über den […]
Eigenanteil" and the Festzuschuss is billed through the KZV.

**What a practice configures:** its KZV's Punktwerte per BEMA part
and Kassenart, its GOZ factor policy and per-item Begründungen, its
lab and material price lists, and the § 2 agreements it uses. It does
not edit either catalog.

### 2. The KZV submission

- BMV-Z § 23 (1): Teil 1 and KFO Zuschüsse "vierteljährlich", Teile 2
  and 4 and Festzuschüsse (Teil 5) "monatlich zu dem von der KZV
  bestimmten Termin, getrennt voneinander"; "grundsätzlich auf
  Datenträgern oder im Wege elektronischer Datenübertragung", per
  Krankenkasse and per Personenkreis M/F/R. § 23 (2): with the
  submission the dentist confirms personal performance and correctness
  incl. real lab costs; § 23 (7): time-barred one year after the
  quarter. § 25 delegates format to the DTA-Vertrag (Anlage 8a), where
  the KZV builds one Einzelfallnachweis per Krankenkasse and
  Behandlungsfall (KZV-Nummer, IK, Krankenversichertennummer, …) and
  the correctness check "durch Einsatz der Prüfregeln des BEMA-Moduls
  in der Zahnarztpraxis und/oder in der KZV unterstützt wird".
- KZBV: "Seit 2012 müssen alle Praxen die vertragszahnärztlichen
  Leistungen mit ihrer KZV in papierloser Form abrechnen. Die KZBV
  entwickelte die notwendigen Abrechnungsmodule […] und stellt sie
  allen Herstellern von Praxisverwaltungssoftware (PVS) zur
  Verfügung." Current modules: Knr12-Modul 5.6/5.7, KCH 6.6/6.7,
  KBR 6.1/6.2, KFO 6.9/7.0, PAR 5.5/5.6, ZE 7.5/7.6, Sendemodul
  3.4/3.5 (versions switch mid-2026). The modules encrypt and send;
  the practice uploads the resulting KCH/KFO/ZE/PAR/KB files on its
  KZV's portal (KZVB: quarterly files in early January/April/July/
  October, monthly files on the 16th). The VSDM Prüfungsnachweis
  travels inside the same submission as eGKO positions (ADR 0032).
- The file format and the module interface are handed to
  manufacturers, not published on the pages read; whether the modules
  are source, a specification or platform binaries, and under what
  licence, is **open** (contact: KZBV-Informatik-ABT@kzbv.de).

### 3. Certification — the rule, verbatim

Anlage 1 BMV-Z, Nr. 1: "Die Verwendung eines Datenverarbeitungssystems,
mit dem der Vertragszahnarzt Leistungen zum Zwecke der Abrechnung
erfasst, speichert und verarbeitet, bedarf der Genehmigung durch die
zuständige Kassenzahnärztliche Vereinigung (KZV). Der Vertragszahnarzt
gibt der KZV das eingesetzte Programmsystem und die jeweils verwendete
Programmversion bekannt […]. Bei elektronischer Abrechnung wird die vom
Vertragszahnarzt verwendete Programmversion automatisch übermittelt.
Ein System ist für die vertragszahnärztliche Abrechnung geeignet, wenn
feststeht, dass programmierte Abrechnungsregeln den jeweils gültigen
Bestimmungen des BMV-Z entsprechen und dass befund- und
leistungsorientierte Abrechnungsautomatismen keine Verwendung finden.
Über die Eignung befindet die Prüfstelle der KZBV. Die Abrechnung
mittels EDV […] und die elektronische Übermittlung der Abrechnung ist
zulässig, wenn die Prüfstelle der KZBV festgestellt hat, dass die
Voraussetzungen hierfür vorliegen. Die KZV widerruft die Genehmigung,
wenn die Voraussetzungen hierfür nicht oder nicht mehr vorliegen."

KZBV Herstellerliste: "Die Auflistung enthält nur kommerzielle
Praxisverwaltungssysteme (PVS), die die Eignungsfeststellung gemäß den
Pflichtvorgaben für zahnärztliche Praxisverwaltungssysteme erhalten
haben. Mit Aussprache der Eignungsfeststellung […] bescheinigt die
KZBV, dass in einem Prüfverfahren die korrekte Verarbeitung der
Abrechnungsdaten und die Einbindung der KZBV-Module sowie die Umsetzung
der aktuell gültigen Vorgaben nachgewiesen wurde." KZVB: "Voraussetzung
für die Online-Einreichung ist ein für den jeweiligen Bema-Teil von der
KZBV als geeignet festgestelltes Abrechnungsprogramm in der aktuellen
Version."

EBZ (Anlage 15 BMV-Z): § 2 (1) presupposes TI connection, TI crypto
and KIM; § 17 (4): flächendeckender Echtbetrieb 01.01.2023 and "Mit
Beginn des Echtbetriebs muss der Vertragszahnarzt mit den
entsprechenden PVS-Modulen ausgestattet sein"; § 17 (1) names "jedes
[…] Softwareverwaltungsprogramm, das das Eignungsfeststellungsverfahren
der KZBV durchlaufen hat"; § 18: paper (Stylesheet, Anlage 14c) only
for technical Störfälle in urgent cases. KZBV: EBZ mandatory since
01.01.2023, ~29 million applications sent.

**Reading.** The answer to the issue's point 3 is yes: a practice may
bill the KZV only with a Programmsystem and version the KZBV Prüfstelle
has found suitable and its KZV has approved, the version is transmitted
with every electronic submission, and the submission files themselves
are produced by the KZBV modules. "Produce the file, don't send it" is
therefore not a scope-down that escapes the rule: the file is the
module's output. Nothing in the texts mentions licences; the obstacle
is the same as Portugal's (ADR 0027): a finding attached to a fixed
version of a program the practice may not modify, plus modules whose
terms of embedding are **open**. A separate design constraint applies
to any German edition: "befund- und leistungsorientierte
Abrechnungsautomatismen" are disqualifying, so no copilot may propose
BEMA positions from findings.

### 4. The private side

What `billing` lacks for a GOZ Rechnung (§ 10 (2)–(4), Anlage 2
Liquidationsvordruck): per line the Leistungsdatum, GOZ/GOÄ number and
name, the tooth (FDI), a Mindestdauer where the catalog names one, the
Steigerungssatz and the amount; a written per-line Begründung whenever
the factor exceeds 2,3 (and, for § 2 agreements, on request); the
"entsprechend" label with the reference position for Analogleistungen;
the "Verlangensleistung" label; § 9 lab costs with the lab invoice
attached and material lines with Bezeichnung, Gewicht and Tagespreis of
alloys; the § 2 (2) agreement and the § 2 (3) Heil- und Kostenplan as
documents; the § 9 (2) Kostenvoranschlag. **VAT:** § 4 Nr. 14 a) UStG
exempts "Heilbehandlungen im Bereich der Humanmedizin, die im Rahmen
der Ausübung der Tätigkeit als […] Zahnarzt […] durchgeführt werden",
but "nicht für die Lieferung oder Wiederherstellung von Zahnprothesen
[…] und kieferorthopädischen Apparaten […], soweit sie der Unternehmer
in seinem Unternehmen hergestellt […] hat" — own-lab prosthetics are
taxable; purely cosmetic work is not a Heilbehandlung (line drawn by
case law, not sourced here). **E-invoicing:** BMF FAQ — the obligation
from 01.01.2025 applies to "Umsätzen zwischen inländischen
Unternehmern"; "Insbesondere private Endverbraucher sind von diesen
Regelungen nicht betroffen", and for § 4 Nr. 8–29 exempt turnovers an
E-Rechnung needs the recipient's consent. Patient invoices carry no
e-invoicing duty.

## Decision

1. **DentalPin, as an open-source product the practice installs and may
   modify, does not seek the KZBV Eignungsfeststellung for the
   statutory (GKV) billing path.** The finding is per Programmsystem
   and version, the version is auto-transmitted with each submission,
   the submission files are the output of KZBV modules whose embedding
   terms are open, and the KZV may revoke its approval.
2. **Statutory billing for a German Kassenpraxis stays with the
   KZBV-listed PVS the practice already runs** (the "connector" here is
   the practice's approved PVS): DentalPin holds the clinical record,
   schedule and private invoicing, and hands treatment data across for
   BEMA billing, EBZ and the quarterly/monthly files. No file is
   generated by DentalPin. Whether the KZBV-Systemwechselschnittstelle
   is documented for such an export is **open**.
3. **The private side is built now, without dependency: module
   `de_goz`**, `DE`-gated, registered through `BillingHookRegistry` in
   the `verifactu` shape: the GOZ Gebührenverzeichnis (and the § 6 (2)
   GOÄ subset) as a versioned seed, Punktzahl × 5,62421 Cent × factor,
   per-line Begründung enforced above 2,3, Analog and Verlangens
   labels, § 9 lab pass-through with attachment, § 2 agreement and
   Heil- und Kostenplan documents, the Anlage 2 layout, VAT exemption
   with the own-lab exception. `billing` learns nothing about Germany.
4. **The BEMA is seeded read-only** (positions, points, parts) for
   documentation, Festzuschuss estimates and the export in point 2 —
   never as a billing engine. Point values are per-clinic settings.
   Whether the BEMA text may be redistributed in a public repository
   is **open** (it is Anlage A to a contract, not a Verordnung).
5. **The German copilot never proposes billable positions from
   findings** (Anlage 1 Nr. 1); recorded here so it is not undone.
6. Two questions are put to KZBV Vertragsinformatik in writing before
   anything else: (a) the form and licence of the Programmmodule and
   whether an open-source, server-hosted product can embed them, and
   (b) whether a certified-edition route — a frozen build filed by a
   German entity — is admissible. A "yes" reopens this ADR as a
   certified edition, as ADR 0027 keeps for Portugal.
7. **Until then DentalPin's position in Germany is "clinical record,
   schedule and private (GOZ) invoicing; statutory billing with your
   KZBV-listed PVS"**, stated on the German pages and in the readiness
   matrix. Together with ADR 0032 this means DentalPin is not the sole
   system of a Kassenpraxis today.

## Consequences

### Good

- The website and the Dampsoft comparison stop hedging; the sentence
  the issue asked for exists and is sourced.
- `de_goz` is real value for every German practice (all PZR, all
  private work, every Eigenanteil invoice) and needs no approval.
- The approach is the same "third party issues, DentalPin mirrors"
  pattern as ADRs 0027/0028; nothing German leaks into `billing`.

### Bad / accepted trade-offs

- A Kassenpraxis keeps two systems; the KZV-facing half is not ours.
- The GOZ and BEMA seeds need an owner for catalog and Punktwert
  updates (BEMA changes yearly, Festzuschüsse yearly).
- The BEMA read-only seed may have to be replaced by a manual import
  if redistribution is refused.

## Alternatives considered

- **Embed the KZBV modules and file for the Eignungsfeststellung
  ourselves.** — Needs the modules' terms and a German filing entity;
  rejected until KZBV answers point 6, kept as the certified-edition
  route.
- **Produce the KCH/ZE/PAR/KFO/KB files without the modules.** — The
  format is not public and the files are the modules' output; the KZV
  would reject an unapproved program version.
- **Re-implement BEMA rules as a plugin to `billing`.** — Billing
  rules in a core module for one country; rejected by the module
  rules and useless without the submission path.
- **Ignore GOZ and ship nothing.** — Leaves the one part that is fully
  open to us on the table.

## How to verify the rule still holds

- `docs/technical/country-readiness.md` and the German landing page
  state "private (GOZ) invoicing in DentalPin; statutory billing with
  a KZBV-listed PVS".
- No module under `backend/app/modules/` writes a KZV submission file
  or claims an Eignungsfeststellung; `de_goz` has no KZV transport.
- Backend test: a `DE` clinic invoice line with factor > 2,3 and no
  Begründung is refused at issue time; an Analog line renders
  "entsprechend" plus the reference number.
- The copilot's German catalog suggestions are limited to GOZ items
  and never derive from periodontogram/odontogram findings.

## Answers to the issue

1. **Catalogs** — Context §1: BEMA parts 1–5, points × a Punktwert
   negotiated per KZV (federal for Teil 5); GOZ points × 5,62421 Cent
   × factor 1,0–3,5 with written Begründung above 2,3; Festzuschüsse
   60/70/75 % on ~50 Befunde via the (electronic) HKP.
2. **Submission** — Context §2: quarterly (Teil 1, KFO) and monthly
   (Teile 2, 4, 5) files per BEMA part, produced by KZBV modules,
   uploaded encrypted to the KZV portal. A self-hosted installation
   cannot produce them without the modules and an approved version.
3. **Certification** — Context §3: yes, required. Anlage 1 BMV-Z Nr. 1
   quoted above; KZBV Eignungsfeststellung per system and version;
   EBZ needs the PVS modules. Scope is therefore "no KZV file", not
   "file without sending".
4. **Private side** — Context §4 and Decision 3: `de_goz`.

## Readiness matrix row

| Germany | ✅ `de` | ❌ | ❌ GOZ private invoicing: `de_goz` module pending (no approval needed); statutory BEMA/KZV billing not possible for a self-hosted, modifiable program — KZBV Eignungsfeststellung is per system and version and the submission files come from KZBV modules (Anlage 1 BMV-Z; ADR 0031) — bill the KZV with a KZBV-listed PVS | ❌ TI: DentalPin talks to the practice's gematik-approved Konnektor/TI-Gateway, never is one; `de_ti` (VSDM first, KIM transport second) pending; EBZ/E-Rezept/ePA stay with the approved PVS (ADR 0032) | #135, #136 (answered) |

## References

- Issue #135; `backend/app/modules/billing/`; ADR 0027 (Portugal),
  ADR 0028 (France), ADR 0032 (TI)
- BMV-Z Gesamtausgabe 01.07.2025 (§ 23, § 25, Anlage 1 Nr. 1–2.4,
  Anlage 10 § 5): <https://www.kzbv.de/wp-content/uploads/bmv-z-2025-07-01-gesamtausgabe.pdf>
- BMV-Z Anlage 8a (DTA-Vertrag): <https://www.gkv-spitzenverband.de/media/dokumente/krankenversicherung_1/zahnaerztliche_versorgung/zae_bmv_z/bmv-z-2022-01-01-anlage-8a.pdf>
- BMV-Z Anlage 15 (EBZ): <https://www.kzbv.de/wp-content/uploads/bmv-z-2025-04-01-anlage-15.pdf>
- BMV-Z Anlagen index (GKV-SV): <https://www.gkv-spitzenverband.de/krankenversicherung/zahnaerztliche_versorgung/bmv_z_ekv_z/bmv_z.jsp>
- BEMA Stand 01.01.2026: <https://www.kzbv.de/wp-content/uploads/KZBV_BEMA_2026-01-01.pdf>;
  KZBV Gebührenverzeichnisse: <https://www.kzbv.de/zahnaerzte/rechtsgrundlagen/bema-und-goz/gebuehrenverzeichnisse/>
- GOZ (BMJ): <https://www.gesetze-im-internet.de/goz_1987/> (PDF
  <https://www.gesetze-im-internet.de/goz_1987/GOZ.pdf>), §§ 2, 5, 6,
  9, 10, Nr. 1040
- § 55 SGB V: <https://www.gesetze-im-internet.de/sgb_5/__55.html>;
  KZBV Festzuschüsse: <https://www.kzbv.de/zahnaerzte/rechtsgrundlagen/festzuschuesse/>;
  KZBV Zahnersatz Antrag bis Abrechnung: <https://www.kzbv.de/patienten/patient-und-krankenkasse/zahnersatz/zahnersatz-antrag-bis-abrechnung/>
- KZBV Programmmodule: <https://www.kzbv.de/zahnaerzte/digitales/praxissoftware/programmmodule/>;
  Herstellerliste: <https://www.kzbv.de/zahnaerzte/digitales/praxissoftware/herstellerliste-und-edv-statistik/>;
  Papierlose Abrechnung: <https://www.kzbv.de/papierlose-abrechnung.98.de.html>;
  EBZ: <https://kzbv.de/ebz>
- KZVB Grundlagen der Abrechnung: <https://www.kzvb.de/abrechnung/grundlagen-der-abrechnung>;
  Abrechnung Online: <https://www.kzvb.de/abrechnung/termine-hilfe/infos-zu-abrechnung-online>
- § 4 Nr. 14 UStG: <https://www.gesetze-im-internet.de/ustg_1980/__4.html>;
  BMF E-Rechnung FAQ: <https://www.bundesfinanzministerium.de/Content/DE/FAQ/e-rechnung.html>
