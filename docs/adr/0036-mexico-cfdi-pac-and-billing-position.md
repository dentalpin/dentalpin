# 0036 — Mexico: CFDI 4.0 is built here and certified by a PAC (`mx_cfdi` connector module)

- **Status:** proposed
- **Date:** 2026-09-12
- **Deciders:** maintainers
- **Tags:** compliance, billing, mexico

## Context

Issue #138 asks what a Mexican practice needs before it can invoice from
DentalPin. The first question is the one ADR 0027 (Portugal) and ADR 0031
(Germany) had to answer: **is there a certification of the *software* that a
self-hosted, modifiable program cannot hold?** For Mexico the answer is no.
Sources read are the primary texts: the CFF as reformed by the DOF decree of
12/11/2021, RMF 2026 (DOF 28/12/2025), Anexo 20 v4.0 (DOF 13/01/2022) and its
Guías de llenado, the SAT cancellation manual and CFDI 4.0 FAQ, LIVA, RLIVA,
LISR art. 151 as published 11/12/2013, and NOM-004-SSA3-2012 (DOF 15/10/2012).
Points not confirmed there are marked **not established**.

### 1. The CFDI, the CSD, and the PAC

A CFDI is an XML document conforming to **Anexo 20 v4.0**, sealed (SHA-256 +
RSA over the cadena original) with the private key of a **Certificado de Sello
Digital** that SAT issues — Anexo 20's validation rule for `Certificado`: *"El
certificado debe ser emitido por el Servicio de Administración Tributaria."*
Any program can do that with the clinic's `.cer`/`.key`. But **CFF art. 29,
fracción IV** requires the CFDI to reach SAT before issue so it validates the
art. 29-A requisitos, assigns the folio and adds SAT's seal, and **CFF art. 29
Bis** puts that act in private hands:

> "El Servicio de Administración Tributaria podrá autorizar a particulares para
> que operen como proveedores de certificación de comprobantes fiscales
> digitales por Internet, a efecto de que: I. Validen el cumplimiento de los
> requisitos establecidos en el artículo 29-A de este Código […] II. Asignen el
> folio del comprobante fiscal digital por Internet. III. Incorporen el sello
> digital del Servicio de Administración Tributaria."

**May a taxpayer self-certify? No.** RMF **2.7.2.1**: *"podrán obtener la
autorización para operar como PCCFDI, las personas morales que tributen
conforme al Título II y Título VII, Capítulo XII de la Ley del ISR, o bien,
conforme al Título III"*, against a long requirement list and, per art. 29 Bis,
a garantía.

What the PAC returns is the **Timbre Fiscal Digital** — Anexo 20, cadena
original, numeral 11: *"El nodo Timbre Fiscal Digital del SAT se integra
posterior a la validación realizada por un proveedor autorizado por el SAT que
forma parte de la Certificación Digital del SAT."* Its required attributes are
`UUID` (the folio fiscal), `FechaTimbrado`, `SelloCFD`, `NoCertificadoSAT` and
`SelloSAT`. RMF **2.7.2.9** adds the PAC's checks: *"Que el periodo entre la
fecha de generación del documento y la fecha en la que se pretende certificar
no exceda de 72 horas"* and that the emisor's CSD *"haya estado vigente en la
fecha de generación del documento enviado y no haya sido cancelado."*

**Therefore:** a self-hosted open-source product can do everything up to and
including the seal — build the XML, sign it with the clinic's own CSD, hand it
to whichever PAC the clinic contracts over that PAC's API, store what comes
back — and can **never** mint the UUID, `FechaTimbrado` or `SelloSAT`. Nothing
here certifies, approves or lists *invoicing software*: the authorisation
attaches to the PAC, the credential to the taxpayer. That is the decisive
difference from Portugal and Germany.

### 2. What a dental clinic needs beyond the invoice

**Complemento de pago (REP).** RMF **2.7.1.32**: *"cuando las
contraprestaciones no se paguen en una sola exhibición, se emitirá un CFDI por
el valor total de la operación […] y posteriormente se expedirá un CFDI por
cada uno de los pagos que se reciban, en el que se deberá señalar 'cero' en el
campo 'Total', sin registrar dato alguno en los campos 'MetodoPago' y
'FormaPago', debiendo incorporar al mismo el 'Complemento para recepción de
Pagos'"*, which *"deberá emitirse a más tardar al quinto día natural del mes
inmediato siguiente al que corresponda el o los pagos recibidos."* That is the
normal case in dentistry. RMF **2.7.1.39** is the escape hatch: if the whole
amount is expected *"a más tardar el último día del mes de calendario en el
cual se expidió el CFDI"* the invoice may be `PUE`; otherwise it is cancelled
and reissued as `PPD` with `FormaPago` "99".

**Cancellation.** CFF **art. 29-A**: *"los comprobantes fiscales digitales por
Internet sólo podrán cancelarse en el ejercicio en el que se expidan y siempre
que la persona a favor de quien se expidan acepte su cancelación"*, and
*"deberán justificar y soportar documentalmente el motivo de dicha
cancelación"*. RMF **2.7.1.34**: the receptor answers *"a más tardar dentro de
los tres días siguientes contados a partir de la recepción de la solicitud"*,
and *"El SAT considerará que el receptor acepta la cancelación del CFDI si
transcurrido el plazo […] no realiza manifestación alguna"* (positiva ficta).
RMF **2.7.1.35** lists the cases needing no acceptance; the live ones for a
clinic are *"Los que amparen montos totales de hasta $1,000.00"* (never a REP),
egresos, CFDI to the RFC genérico `XAXX010101000`, and *"Cuando la cancelación
se realice dentro del día hábil siguiente a su expedición."* Every request
carries a **motivo**: Anexo 20's cancellation schema makes `Motivo`
`use="required"` with `Valores Permitidos 01 02 03 04`, and `FolioSustitucion`
*"es requerido cuando la clave del motivo de cancelación es 01"*. Order matters
(FAQ 42): issue the corrected CFDI first, relating it as "04" (Sustitución de
los CFDI previos), *then* cancel with motivo "01" quoting the new folio. A CFDI
with live related documents is *No Cancelable* until those are cancelled,
except under motivo "01".

**`UsoCFDI` D01.** The Guía lists `D01 = Honorarios médicos, dentales y gastos
hospitalarios`, personas físicas only, bound to the receiver: *"el valor
registrado en el campo RegimenFiscalReceptor, debe corresponder a un valor de
la columna Régimen Fiscal Receptor de dicho catálogo."* D01 matters for **LISR
art. 151, fracción I**, which conditions the deduction on the payment method:

> "Los pagos por honorarios médicos y dentales, así como los gastos
> hospitalarios […] y se efectúen mediante cheque nominativo del contribuyente,
> transferencias electrónicas de fondos, desde cuentas abiertas a nombre del
> contribuyente en instituciones que componen el sistema financiero […] o
> mediante tarjeta de crédito, de débito, o de servicios."

Cash does not qualify, and RMF **3.17.10** puts dentistry squarely inside
fracción I: *"se consideran incluidos en los pagos por honorarios dentales los
efectuados a estomatólogos […] Cirujano Dentista, Licenciado en Estomatología
[…] cuando la prestación de los servicios requiera título de médico conforme a
las leyes."* A clinic taking cash can issue a valid CFDI that is useless to the
patient.

**Régimen fiscal and RFC.** CFF art. 29-A fracc. I requires *"La clave del
Registro Federal de Contribuyentes, nombre o razón social de quien los expida y
el régimen fiscal en que tributen"*; fracc. IV, of the receiver, *"La clave del
Registro Federal de Contribuyentes, nombre o razón social; así como el código
postal del domicilio fiscal de la persona a favor de quien se expida, asimismo,
se debe indicar la clave del uso fiscal que el receptor le dará al comprobante
fiscal."* The Guía adds that the receiver's RFC *"debe estar contenido en la
lista de RFC (l_RFC) inscritos no cancelados en el SAT"* unless generic: name,
RFC and CP must match the patient's Constancia de Situación Fiscal or the stamp
is rejected.

### 3. IVA on dental services

**LIVA art. 15, fracción XIV** exempts *"Los servicios profesionales de
medicina, cuando su prestación requiera título de médico conforme a las leyes,
siempre que sean prestados por personas físicas, ya sea individualmente o por
conducto de sociedades civiles o instituciones de asistencia o beneficencia
privada autorizadas por las leyes de la materia."* **RLIVA art. 41**: *"los
servicios profesionales de medicina por los que no se está obligado al pago del
impuesto, son los de médico, médico veterinario o cirujano dentista."* The
exemption turns on *who* bills — a persona física or sociedad civil, not an
S.A. de C.V.; goods are at 16 %.

In the XML this is per concepto: `ObjetoImp` "02" with
`Impuestos/Traslados/Traslado` carrying `TipoFactor` = `Exento` and no
`TasaOCuota`. A compliant patient invoice therefore carries emisor RFC +
régimen; receptor RFC + nombre + CP + `RegimenFiscalReceptor` + `UsoCFDI` D01;
`LugarExpedicion`; `Exportacion` "01"; `MetodoPago` PUE/PPD; the real
`FormaPago`; one concepto per treatment with `ClaveProdServ` and
`ObjetoImp`/`TipoFactor`; and, after stamping, the TFD block with QR and cadena
original.

### 4. NOM-004-SSA3-2012 — the electronic expediente

**Retention**, numeral 5.4: *"por tratarse de documentos elaborados en interés
y beneficio del paciente, deberán ser conservados por un periodo mínimo de 5
años, contados a partir de la fecha del último acto médico."* **Signature**,
numeral 5.10: *"Todas las notas en el expediente clínico deberán contener
fecha, hora y nombre completo de quien la elabora, así como la firma autógrafa,
electrónica o digital, según sea el caso; estas dos últimas se sujetarán a las
disposiciones jurídicas aplicables."* **Electronic form**, numeral 5.12: *"De
manera optativa, se podrán utilizar medios electrónicos, magnéticos […] o de
cualquier otra tecnología en la integración de un expediente clínico, en los
términos de las disposiciones jurídicas aplicables."*

**Is any Mexican certification of the software required? No.** NOM-004
regulates the *expediente* — contents, custody, signatures — never the program
holding it: no numeral requires certification, authorisation or approval of
software, and it establishes no register of approved systems. With §1 that is
the finding separating Mexico from Portugal.

## Decision

1. **DentalPin builds, validates and seals the CFDI 4.0 itself; a PAC certifies
   it.** No Mexican authority certifies invoicing or clinical software (CFF 29
   Bis authorises *providers*; NOM-004 regulates the *record*), so the
   Portugal/Germany blocker does not exist and we implement the module.
2. **Module `mx_cfdi`, `MX`-gated, in the `verifactu` shape**: own `mx_cfdi_*`
   tables, own Alembic branch (`branch_labels=("mx_cfdi",)`), own Nuxt layer,
   `depends=["billing","catalog"]`, registered through `BillingHookRegistry`
   only when the clinic's country is `MX`; uninstall leaves nothing behind and
   `billing` learns nothing about Mexico.
3. **The clinic holds its CSD**, uploaded like the FNMT certificate in
   `verifactu` (`.cer` + `.key` + password, encrypted at rest); we never
   generate, request or escrow one.
4. **The PAC is the clinic's contract, behind a driver interface.** On
   `on_invoice_issued` we build and seal the XML, persist it `pending`, and a
   worker drains the queue inside the 72-hour window, storing UUID,
   `FechaTimbrado`, `SelloSAT`, `NoCertificadoSAT` and the stamped XML in
   `Invoice.compliance_data['MX']` — the stamped XML is the legal document.
5. **Cancellation is a state machine, not a delete**: motivo 01–04,
   `FolioSustitucion` mandatory on 01, substitution issued *before* the request,
   related-CFDI check first, the three-working-day window polled, the
   same-ejercicio limit enforced in the UI.
6. **REP is first-class.** `PPD` invoices open a payment schedule; every payment
   produces a REP due by the 5th natural day of the following month; `PUE` only
   under rule 2.7.1.39, with its reissue path.
7. **IVA exemption is configuration, not a constant.** The clinic declares its
   régimen and legal form; the module maps catalog `vat_types` to
   `ObjetoImp`/`TipoFactor` as `verifactu` maps AEAT classifications.
8. **D01 carries a deduction warning.** When `UsoCFDI` is D01 and `FormaPago` is
   `01` (Efectivo), the UI warns that the patient loses the LISR 151-I
   deduction; we never rewrite the real form of payment.
9. **No NOM-004 work is gated on certification**, but the `MX` profile must meet
   5.4/5.10/5.12: five-year retention, every note stamped with author and time.

## Consequences

### Good

- Mexico becomes implementable instead of a "no", and the pattern is
  `verifactu`'s almost mechanically (build → sign → queue → acknowledgement →
  PDF), which is what #138 asked for.
- The clinic keeps its own CSD and picks its own PAC; we take no fiscal custody,
  operate no service, and cancellation and REP — what really shapes the state
  machine — are specified before a line of code.

### Bad / accepted trade-offs

- We depend on a commercial PAC's API and uptime, and the first driver will leak
  its assumptions into the interface.
- SAT catalogs (`c_ClaveProdServ`, `c_UsoCFDI`, `c_RegimenFiscal`,
  `c_FormaPago`, `c_ObjetoImp`) need a seed and an update owner.
- The same-ejercicio limit and the three-day window make December and January
  corrections hard; patient fiscal data must be accurate or stamps fail.

## Alternatives considered

- **Connector to a third-party invoicing SaaS (the Portugal answer).** —
  Unnecessary here: a second subscription and a lost invoice template for no
  legal gain.
- **Become a PAC.** — RMF 2.7.2.1 restricts authorisation to qualifying
  personas morales with a garantía and continuous supervision.
- **Ship a "CFDI-ready" export and stamp elsewhere.** — Leaves cancellation,
  REP and the UUID round-trip outside the product.
- **Treat every invoice as PUE, or hardcode IVA exempt for all dental lines.**
  — The first contradicts RMF 2.7.1.32; the second ignores that LIVA 15-XIV is
  conditioned on the provider's form (RLIVA 41).

## How to verify the rule still holds

- `docs/technical/country-readiness.md` and the Mexican landing page say "CFDI
  4.0 issued from DentalPin, stamped by your PAC" — never "certified software".
- Backend test: `mx_cfdi` never writes a `UUID`, `FechaTimbrado`, `SelloSAT` or
  `NoCertificadoSAT` of its own; all four arrive only in a PAC response.
- Backend test: a `PPD` invoice cannot be settled without a REP; a REP is never
  cancellable under the ≤ $1,000 rule; motivo `01` without `FolioSustitucion` is
  refused, and so is cancelling a CFDI with a live related CFDI.
- Grep: no Mexico-specific column in `invoices`/`invoice_items`.
- Annual RMF check: rules 2.7.1.32, 2.7.1.34, 2.7.1.35, 2.7.1.39 and 2.7.2.9
  keep both their numbers and their content.

## Answers to the issue

1. **Version and schema** — Anexo 20 v4.0 (DOF 13/01/2022); dental fields per
   §2–§3. No healthcare complemento exists; the only one a clinic needs is
   **Pagos (REP)**. IVA exemption is `ObjetoImp` + `TipoFactor=Exento`.
2. **Stamping route** — the clinic contracts the PAC; DentalPin holds its CSD
   and the PAC credentials, seals the XML and sends it within 72 h.
   Self-certification is impossible (CFF 29 Bis; RMF 2.7.2.1).
3. **Cancellation** — §2: motivo 01–04, acceptance unless RMF 2.7.1.35 applies,
   three working days with positiva ficta, substitution first, ejercicio limit.
4. **Payment complements** — yes: a REP per payment, by the 5th natural day of
   the following month (RMF 2.7.1.32).
5. **Retention** — NOM-004 numeral 5.4: five years from the last clinical act.
   The CFF art. 30 term for CFDI and PAC acuses is **not established**.

## Open questions

- **Not established:** the CFF art. 30 retention term for CFDI and PAC
  acknowledgements — the DOF 2021 decree elides the unchanged paragraphs.
- **Not established:** whether NOM-004 numeral 5.10's "firma electrónica o
  digital" requires e.firma for clinical notes; it defers to unnamed
  "disposiciones jurídicas aplicables".
- **Not established:** the labels of cancellation motivos 02, 03 and 04 (only
  "01 Comprobante emitido con errores con relación" appears verbatim in the
  sources read); take them from `c_MotivoCancelacion`.
- **Not established:** whether LISR art. 151-I has been amended since
  11/12/2013 (diputados.gob.mx was unreachable); the payment-means condition is
  quoted from the published text and confirmed operative by RMF 2026 rule
  3.17.10.
- **Not established:** which PAC to drive first, and whether any offers a CI
  sandbox.

## Readiness matrix row

| Mexico | ✅ `es` | ✅ | ❌ CFDI 4.0 (Anexo 20 v4.0) is issuable from a self-hosted, modifiable program — **no Mexican certification of invoicing or clinical software exists**; the clinic holds its own CSD, DentalPin builds and seals the XML and an authorised PAC adds the timbre fiscal digital (CFF 29 Bis; RMF 2.7.2.1) — `mx_cfdi` module pending (CFDI + REP + cancellation 01–04, IVA exento per LIVA 15-XIV / RLIVA 41) (ADR 0036) | n/a — NOM-004-SSA3-2012 requires no software certification: five-year retention, signed notes | #138 (answered) |

## References

- Issue #138; `backend/app/modules/verifactu/`, `docs/modules/verifactu.md`;
  ADR 0027 (Portugal), ADR 0031 (Germany)
- CFF arts. 29, 29 Bis, 29-A — reform decree, DOF 12/11/2021. LIVA art. 15-XIV;
  RLIVA art. 41
- RMF 2026, DOF 28/12/2025 — rules 2.7.1.32, 2.7.1.34, 2.7.1.35, 2.7.1.39,
  2.7.1.45, 2.7.2.1, 2.7.2.9, 3.13.29, 3.17.10
- Anexo 20 v4.0, DOF 13/01/2022 (Comprobante, Timbre Fiscal Digital 1.1,
  cancellation schema); SAT *Guía de llenado de los CFDI*, *Guía … complemento
  para recepción de pagos*, *Cancelación de facturas — Manual de usuario*
  (2022), *Preguntas frecuentes CFDI 4.0* q. 42:
  <https://www.sat.gob.mx/personas/factura-electronica>
- LISR art. 151-I as published, DOF 11/12/2013:
  <https://dof.gob.mx/nota_detalle.php?codigo=5325373&fecha=11/12/2013>
- NOM-004-SSA3-2012, *Del expediente clínico*, numerales 5.4, 5.10, 5.12, DOF
  15/10/2012: <https://dof.gob.mx/nota_detalle.php?codigo=5272787&fecha=15/10/2012>
