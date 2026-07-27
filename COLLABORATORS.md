# DentalPin Collaborators Policy

> Version 1.0 — April 2026
> Author: Dentared Odontology Services S.L. (hereinafter, **Dentaltix**, the project maintainer)

> 🇬🇧 English version below. 🇪🇸 Versión en español más abajo.

---

## 🇬🇧 English

DentalPin aims to become the open standard for dental clinic management: the operating system that connects clinics, professionals, suppliers, software and services across the ecosystem. For that standard to be credible and durable, its core must be **open, neutral and independent**.

If you're reading this, you probably want to build something on top of DentalPin. **Welcome.** We're glad you're here. This document exists so that you understand, with no fine print, what we offer you, what we ask from you, and why some things will not move. We believe honesty from day one is what makes collaborations last for years.

If you decide to join the ecosystem, you accept the principles set out below.

---

### 1. Vision

- **Open standard.** DentalPin exists so that any clinic, in any country, can run its operation with software that is free, audited and portable.
- **Multilateral ecosystem.** The project's value grows when others build on top of it: clinical modules, lab integrations, digital orthodontics, radiology, billing, AI, automation, marketplaces, etc.
- **Free official SaaS on top of the core.** Dentaltix will operate a SaaS where core usage is free for clinics. Clinics only pay for the paid modules and integrations they choose to activate.
- **Sustainability without capture.** Collaborators monetize their modules. Dentaltix monetizes the SaaS operation and a marketplace commission. The core itself is never monetized.

---

### 2. Non-negotiable principles

We start here because these are the pillars that allow us to offer everything else. They are not negotiated with anyone — and precisely because they are not negotiated with anyone, they also protect you: nobody will be able to use the project against you tomorrow.

1. **Single core maintainer.** Dentared Odontology Services S.L. is the only entity that maintains, directs and publishes the DentalPin core. There is no co-ownership, no shared governance, and no reserved seats for collaborators in core technical decisions.
2. **License and conversion.** The core is distributed under BSL 1.1, automatically converting to Apache 2.0 four years after each release. The license will not be downgraded to the detriment of the community.
3. **Protected trademark.** "DentalPin" and the associated logos are trademarks of Dentared Odontology Services S.L. Collaborators may indicate compatibility ("Compatible with DentalPin", "Module for DentalPin") according to the brand guidelines, but may not use the trademark as their own, nor in their company name, domain or product.
4. **Mandatory CLA.** Every contribution to the core repository requires signing a Contributor License Agreement that grants Dentaltix the rights necessary to maintain, relicense (within OSI-approved licenses) and defend the project. The CLA does not transfer authorship: the contributor remains the holder of their work.
5. **Strict technical boundary.** Core and modules are separated by explicit contracts: module manifests, declared dependencies, event bus, and versioned public APIs. No module may modify the core for its own benefit. Extensions go through public APIs or through an open proposal (RFC).
6. **Competitive neutrality.** The core does not favor any collaborator. If Dentaltix builds a module in a category where collaborators already exist, it does so using exactly the same APIs and marketplace rules as any third party, and discloses itself as such.
7. **Clinical data portability.** Clinics always own their data. No module, integration, or official SaaS configuration may prevent the full export of a clinic's data.

---

### 3. Ecosystem model

DentalPin is an **open core with marketplace**. Three layers:

| Layer | Maintainer | Distribution |
|------|-------------------|--------------------|
| **Core** | Dentaltix exclusively | Open source (BSL 1.1 → Apache 2.0) |
| **Official modules** | Dentaltix, open | Open source, part of the main repository |
| **Third-party modules** | Any collaborator | DentalPin marketplace; can be open source or proprietary |

The official SaaS operated by Dentaltix is the default distribution channel, but the project remains self-hostable. Any clinic or technical partner may deploy DentalPin on their own.

---

### 4. What we offer collaborators

In exchange for building on DentalPin with quality and respect for these principles, collaborators receive concrete value:

- **Distribution.** Access to the marketplace integrated in the official SaaS, with exposure to every active clinic.
- **Stable, documented APIs.** Semantic versioning commitment for public APIs, minimum 12-month deprecation window, and a published catalog of events.
- **Transparent revenue share.** Dentaltix acts as the marketplace's payment processor. Standard commission published and applied equally to all collaborators.
- **Co-marketing.** Success stories, featured listings, joint content, presence at ecosystem events.
- **Technical voice.** Any collaborator may propose changes to the APIs or new extension points through public RFCs. Dentaltix discusses them openly. Final decisions belong to Dentaltix; the debate belongs to the community.
- **Early access to the roadmap.** Early access to preliminary APIs and roadmap information, under NDA where applicable.

Collaborators who join in the project's initial phase also receive enhanced benefits — see §5.

---

### 5. Founding Partners program

Betting on a young ecosystem with little adoption is not free. We know that. **Founding Partners** are the collaborators who jump in when there is more vision than clinics, and we want to repay that bet generously — not only in the first few months, but for as long as the module remains alive.

#### Benefits

- **0% marketplace commission for 18 months** from the activation of their module, on all sales through the official SaaS.
- **50% discount on the standard commission from month 19 onwards**, indefinitely, for as long as the module remains active and the collaborator continues to meet the program's commitments. This perpetual discount is how we recognize, also over time, those who trusted first.
- **Co-design of APIs in their category.** Technical seat at the design of APIs and events relevant to their area (not a binding vote, but priority input that is answered in writing).
- **Early access** to roadmap, preliminary APIs, and test environments, with reasonable time to adapt before the general community.
- **Featured placement** in the marketplace and official materials during the first 18 months.
- **Priority co-marketing.** Joint success story, coordinated content, presence at events where Dentaltix participates.
- **Direct line** to Dentaltix's technical team (dedicated channel, business-day response SLA).
- **Access to aggregated, anonymized marketplace metrics** that support their business decisions (no identifiable data of clinics or other collaborators).
- **Perpetual recognition.** The "Founding Partner since [year]" badge and the mention on the official partners page remain as long as the module stays active and meets the commitments, even when other collaborators join the ecosystem.
- **Reinforced Dentaltix commitments** (see §6) applied with greater rigor: early notice of structural changes, preferential treatment during coexistence periods, priority in technical reviews.

#### What we ask in return

- A quality module, in production, with real support behind it.
- Honest feedback — the good and the uncomfortable — on APIs, documentation, onboarding, and friction points.
- Willingness to do a joint success story when the time comes.
- Good faith: no using early access to erode the ecosystem or to build a competitive fork.

#### What the program is **not**

To avoid misunderstandings: being a Founding Partner does not imply co-ownership, exclusivity, binding vote on the core, or perpetual full-fee waiver. It is a "first wave" agreement, generous and time-bound, designed to make starting alongside you worthwhile — it is not a concession over the project.

The program contemplates **a maximum of 5 Founding Partners per country** (not 5 worldwide). Each country DentalPin enters operates its own Founding Partner cohort, with its own slots, opening date and category map. There is no rush to fill them: the slots are deliberately few, because we want to choose carefully who we start this with in each market. Within a given country, each slot is reserved for a different category of the ecosystem (automated agenda, patient communication, clinical AI, lab integrations, etc.); no more than one slot per category per country.

---

### 6. Dentaltix's commitments to collaborators

This is not a one-way street. If we ask you for quality, support and good faith, the fair thing is for you to know exactly what to expect from us:

- **Stable APIs.** Semantic versioning, minimum 12-month deprecation window, public changelog.
- **Early communication.** Structural changes to the core, marketplace model or SaaS policies are communicated to active collaborators with reasonable notice. For Founding Partners and Strategic, before the general public.
- **No opportunistic cannibalization.** If Dentaltix decides to build an official module in a category where there is already a Strategic or Founding Partner module that is active and compliant with this policy, it will give a minimum of **6 months' notice** and will maintain a reasonable coexistence period. The Dentaltix module will use exactly the same APIs as any third party, with no privileged shortcuts.
- **Timely payments.** Marketplace settlements within published deadlines, with clear breakdown and traceability.
- **Public defense of neutrality.** Dentaltix takes responsibility for keeping ecosystem neutrality visible and for acting when any actor — including itself — tries to break it.
- **Recognition of the early bet.** Those who bet on the project in its early phase will keep the Founding Partner recognition while they meet the basic commitments, also when bigger players arrive.
- **No legal surprises.** This policy is not modified retroactively to the detriment of agreements signed with Founding Partners during the term of their agreement (see §12).

These commitments don't stay in a PDF: they also appear, in writing, in the agreement we sign with you.

---

### 7. What we cannot offer you (and why it suits you)

With the same care with which we say yes to many things, there are others to which we will always answer "no". It's not distrust or rigidity: it's what keeps the ecosystem neutral and, above all, what protects your investment in it against actors who arrive later.

- **Co-ownership or co-governance of the core.** No collaborator, however senior or strategic, gets a binding vote over the core, veto rights, or participation in its roadmap beyond the public voice through RFCs.
- **Exclusivity by category.** No functional or territorial exclusivity is granted. If you join as an agenda-automation module, others can also join in agenda automation. That same rule prevents another player from blocking you tomorrow.
- **Custom changes to the core.** The core is not modified to favor a particular collaborator's business case. If an API does not exist, it is proposed via RFC and evaluated on its general value, not on who is asking for it.
- **Favorite forks.** No fork of the core is recognized, recommended, or supported, except for legitimate self-hosted deployments by clinics or technical partners.
- **Equity, IP or shared branding.** A technical or commercial collaboration generates no rights over Dentared Odontology Services S.L., over the core code, or over the DentalPin trademark.
- **Privileged access to clinic data.** Clinical data belongs to the clinics. No collaborator accesses aggregated or disaggregated data without the explicit consent of the owning clinic.

> **Why these limits also protect you.** If today we sold exclusivity or co-governance to the first arrival, tomorrow you would have to negotiate against someone with bigger muscle. The symmetric rule — the same for everyone — is the only one that holds long-term, and that's why it's also the best guarantee we can give you.

---

### 8. Collaboration tiers

| Tier | For whom | Requirements | Benefits |
|-------|-----------|------------|------------|
| **Community** | Any developer or organization | Publishable module, complies with technical and legal guide | Marketplace listing, standard commission |
| **Verified** | Collaborators with a module in production and demonstrable support | Technical review, minimum SLA, public support policy | "Verified" badge, improved placement, occasional co-marketing |
| **Strategic** | Collaborators in key categories or with significant traction | Written agreement, reinforced quality and support commitments | Priority treatment in RFCs, co-marketing, early notice of structural changes |
| **Founding Partner** | First collaborators in the project's initial phase | Written agreement; see §5 | Full benefits of the Founding Partners program |

Tier promotions are at Dentaltix's discretion and based on published objective criteria (quality, support, adoption, alignment with this policy). The Founding Partner tier is a time-bound program; the others remain open.

---

### 9. Collaborator commitments

In turn, anyone publishing a module or integration in the DentalPin ecosystem assumes these commitments — the same you would expect from any provider entering a clinic:

1. **Technical quality.** Comply with the module-creation guide (`docs/technical/creating-modules.md`), pass review and tests.
2. **Support.** Publish channel and SLA. Keep the module compatible with the supported DentalPin versions.
3. **Legal compliance.** Respect GDPR and the applicable clinical-data regulations in each jurisdiction where it operates. Data processor agreement duly formalized when applicable.
4. **Transparency with the clinic.** Clear pricing, clear cancellation terms, module data export always available to the clinic.
5. **No hostile fork.** Do not promote, distribute or recommend competitive forks of the core while part of the official ecosystem.
6. **Correct trademark use.** Follow the brand and co-branding guidelines published by Dentaltix.
7. **Conflicts of interest.** Disclose any relevant interest (cross-shareholdings, exclusivity agreements with third parties, etc.) that may affect ecosystem neutrality.

If something breaks, we talk first. Only if the issue cannot — or will not — be fixed would we suspend a module from the marketplace or remove a collaborator from the program. Always with a remediation period when the problem is fixable, and always in writing.

---

### 10. Economics (high-level summary)

- **Free core SaaS** for clinics. Cost covered by marketplace margin and premium services operated by Dentaltix (dedicated hosting, support, advanced compliance, etc.).
- **Third-party modules**: price set by the collaborator. Dentaltix acts as payment processor and applies a standard commission, identical for all collaborators in the same tier. While there is no public partner portal, concrete figures are agreed in writing in each marketplace contract; once the portal exists, they will be published openly.
- **What that commission funds.** It is not opportunistic margin: it funds continuous core development and maintenance, the infrastructure of the free official SaaS for clinics, marketplace payment processing, and first-line support. Without that commission, neither the open core nor the free SaaS would be sustainable long-term.
- **Founding Partners**: 0% commission during the **first 18 months** from the activation of their module in the marketplace, and **50% discount on the standard commission from month 19 onwards**, indefinitely, while the module remains active and the collaborator continues to meet the program's commitments. The program admits a **maximum of 5 Founding Partners per country**, not 5 worldwide.
- **Settlements**: cycle and conditions published in the marketplace agreement.

Concrete figures may be updated with reasonable notice, and any change is applied uniformly to all collaborators in the same tier. Today they live in the individual agreements; once the public partner portal exists, they will be published openly there.

---

### 11. Onboarding process

1. **Initial contact** by writing to **ramon.martinez@dentaltix.com**. In this initial phase of the project, there is no form or portal yet: I, Ramón, founder of Dentaltix, handle every partner conversation personally.
2. **Fit conversation**: use case, category, business model, alignment with this policy.
3. **Written agreement**: marketplace contract and, if applicable, Founding Partner or Strategic addendum.
4. **Module development** following the technical guide.
5. **Technical and legal review** by Dentaltix.
6. **Publication** in the marketplace.
7. **Ongoing operation**: metrics, support, renewal.

There will be cases where we don't fit, and when that happens we'll tell you openly and with reasons: when an onboarding conflicts with this policy, with ecosystem neutrality, or with the interests of the clinics using the platform.

---

### 12. Changes to this policy

This policy will evolve with the project — it would be strange if it didn't. When we change it:

- Changes are published with version number and changelog.
- Active collaborators are notified with reasonable advance notice.
- **They are not applied retroactively to the detriment of agreements signed with Founding Partners or Strategic during the term of their agreement.**

The current policy is always the one published in this file of the official repository.

---

### 13. Contact

DentalPin is in a very early phase, so for now the channel is direct and personal: **ramon.martinez@dentaltix.com**. I'm Ramón, founder of Dentaltix, and I personally handle every conversation with collaborators. As the team and adoption grow, we will open dedicated channels (`partners@`, `brand@`, partner portal) and announce them here.

- Want to explore a collaboration? Write to me and we'll sit down as soon as possible to see if it makes sense.
- Brand or logo matters? Same email, mention it in the subject.
- Something in this policy unclear or off-putting? You can open a public issue in the repository tagged `governance` — we prefer to discuss these things in the open — or write to me directly.

---

*DentalPin belongs to the clinics that use it, the developers who contribute, and the dental ecosystem that adopts it. Dentaltix is the steward that makes sure that share-out remains fair — and that includes protecting the bet of those who collaborate from the very beginning.*

---
---

## 🇪🇸 Español

DentalPin aspira a convertirse en el estándar abierto para la gestión de clínicas dentales: el sistema operativo que conecta a clínicas, profesionales, proveedores, software y servicios del ecosistema. Para que ese estándar sea creíble y duradero, su núcleo debe ser **abierto, neutral e independiente**.

Si estás leyendo esto, probablemente quieras construir algo encima de DentalPin. **Bienvenido.** Nos encanta que estés aquí. Este documento existe para que entiendas, sin letra pequeña, qué te ofrecemos, qué te pedimos y por qué algunas cosas no se mueven. Pensamos que la honestidad desde el primer minuto es lo que hace que las colaboraciones aguanten años.

Si decides sumarte al ecosistema, das por aceptados los principios que vienen a continuación.

---

### 1. Visión

- **Estándar abierto.** DentalPin existe para que cualquier clínica, en cualquier país, pueda gestionar su operativa con un software libre, auditado y portable.
- **Ecosistema multilateral.** El valor del proyecto crece cuando otros construyen sobre él: módulos clínicos, integraciones con laboratorios, ortodoncia digital, radiología, facturación, IA, automatización, marketplaces, etc.
- **SaaS oficial gratuito sobre el core.** Dentaltix operará una versión SaaS cuyo uso del core es gratis para las clínicas. Las clínicas pagan únicamente por los módulos e integraciones de pago que decidan activar.
- **Sostenibilidad sin captura.** Los colaboradores monetizan sus módulos. Dentaltix monetiza la operación del SaaS y una comisión sobre el marketplace. El core nunca se monetiza por sí mismo.

---

### 2. Principios innegociables

Empezamos por aquí porque son los pilares que nos permiten ofrecer todo lo demás. No se negocian con nadie —y precisamente porque no se negocian con nadie, también te protegen a ti: nadie podrá usar el proyecto en tu contra mañana.

1. **Único mantenedor del core.** Dentared Odontology Services S.L. es la única entidad que mantiene, dirige y publica el core de DentalPin. No hay co-propiedad, ni gobernanza compartida, ni asientos reservados para colaboradores en las decisiones técnicas del core.
2. **Licencia y conversión.** El core se distribuye bajo BSL 1.1, con conversión automática a Apache 2.0 a los 4 años de cada release. La licencia no se modificará a la baja en perjuicio de la comunidad.
3. **Marca protegida.** "DentalPin" y los logotipos asociados son marca de Dentared Odontology Services S.L. Los colaboradores pueden indicar compatibilidad ("Compatible con DentalPin", "Módulo para DentalPin") según las guías de marca, pero no usar la marca como suya ni en denominación social, dominio o producto.
4. **CLA obligatorio.** Toda contribución al repositorio del core requiere firmar un Contributor License Agreement que otorga a Dentaltix los derechos necesarios para mantener, relicenciar (dentro de licencias OSI-aprobadas) y defender el proyecto. El CLA no transfiere la autoría: el contribuidor sigue siendo titular de su trabajo.
5. **Frontera técnica estricta.** El core y los módulos están separados por contratos explícitos: manifiestos de módulo, dependencias declaradas, bus de eventos y APIs públicas versionadas. Ningún módulo puede modificar el core para su propio beneficio. Las extensiones pasan por las APIs públicas o por una propuesta abierta (RFC).
6. **Neutralidad competitiva.** El core no favorece a ningún colaborador. Si Dentaltix construye un módulo en una categoría donde ya existen colaboradores, lo hace usando exactamente las mismas APIs y reglas del marketplace que cualquier tercero, y se declara como tal.
7. **Portabilidad de los datos clínicos.** Las clínicas son siempre propietarias de sus datos. Ningún módulo, integración o configuración de la SaaS oficial puede impedir la exportación íntegra de los datos de una clínica.

---

### 3. Modelo de ecosistema

DentalPin es un **open core con marketplace**. Tres capas:

| Capa | Quién la mantiene | Cómo se distribuye |
|------|-------------------|--------------------|
| **Core** | Dentaltix en exclusiva | Open source (BSL 1.1 → Apache 2.0) |
| **Módulos oficiales** | Dentaltix, abiertos | Open source, parte del repositorio principal |
| **Módulos de terceros** | Cualquier colaborador | Marketplace de DentalPin; pueden ser open source o propietarios |

El SaaS oficial operado por Dentaltix es la vía de distribución por defecto, pero el proyecto sigue siendo auto-hospedable. Cualquier clínica o partner técnico puede desplegar DentalPin por su cuenta.

---

### 4. Qué ofrecemos a los colaboradores

A cambio de construir sobre DentalPin con calidad y respeto a estos principios, los colaboradores reciben valor concreto:

- **Distribución.** Acceso al marketplace integrado en la SaaS oficial, con presencia ante todas las clínicas activas.
- **APIs estables y documentadas.** Compromiso de versionado semántico para las APIs públicas, ventana mínima de deprecación de 12 meses y catálogo de eventos publicados.
- **Revenue share transparente.** Dentaltix actúa como procesador de pagos del marketplace. Comisión estándar publicada y aplicada por igual a todos los colaboradores.
- **Co-marketing.** Casos de éxito, listados destacados, contenido conjunto, presencia en eventos del ecosistema.
- **Voz técnica.** Cualquier colaborador puede proponer cambios a las APIs o nuevos puntos de extensión mediante RFCs públicos. Dentaltix los discute en abierto. La decisión final es de Dentaltix; el debate es de la comunidad.
- **Early access al roadmap.** Acceso anticipado a APIs preliminares y a información del roadmap bajo NDA cuando aplique.

Los colaboradores que entren en la fase inicial del proyecto reciben además beneficios reforzados —ver §5.

---

### 5. Programa Founding Partners

Apostar por un ecosistema joven, con poca adopción, no es gratis. Lo sabemos. Los **Founding Partners** son los colaboradores que se suben cuando todavía hay más visión que clínicas, y queremos que esa apuesta os la devolvamos con creces —no solo en los primeros meses, sino mientras el módulo siga vivo.

#### Beneficios

- **Comisión 0% de marketplace durante 18 meses** desde la activación de su módulo, sobre todas las ventas a través de la SaaS oficial.
- **50% de descuento sobre la comisión estándar a partir del mes 19**, de forma indefinida mientras el módulo siga activo y el colaborador siga cumpliendo los compromisos del programa. Este descuento perpetuo es la forma en la que reconocemos, también con el tiempo, a quienes confiaron primero.
- **Co-diseño de APIs en su categoría.** Asiento técnico en el diseño de las APIs y eventos relevantes para su área (no es voto vinculante, pero sí input prioritario y respondido por escrito).
- **Acceso temprano** a roadmap, APIs preliminares y entornos de prueba, con tiempo razonable para adaptarse antes que la comunidad general.
- **Placement destacado** en el marketplace y materiales oficiales durante los primeros 18 meses.
- **Co-marketing prioritario.** Caso de éxito conjunto, contenido coordinado, presencia en eventos donde Dentaltix participe.
- **Línea directa** con el equipo técnico de Dentaltix (canal dedicado, SLA de respuesta en días laborables).
- **Acceso a métricas agregadas y anonimizadas del marketplace** que ayuden a su decisión de negocio (sin datos identificables de clínicas o de otros colaboradores).
- **Reconocimiento perpetuo.** El badge "Founding Partner desde [año]" y la mención en la página oficial de partners se mantienen mientras el módulo siga activo y cumpla los compromisos, incluso cuando otros colaboradores se sumen al ecosistema.
- **Compromisos reforzados de Dentaltix** (ver §6) aplicados con mayor rigor: aviso anticipado de cambios estructurales, tratamiento preferente en periodos de coexistencia, prioridad en revisiones técnicas.

#### Qué te pedimos a cambio

- Un módulo de calidad, en producción, con soporte real detrás.
- Feedback honesto —del bueno y del incómodo— sobre APIs, documentación, onboarding y puntos de fricción.
- Que estés dispuesto a hacer un caso de éxito conjunto cuando llegue el momento.
- Buena fe: no usar el acceso temprano para erosionar el ecosistema ni para construir un fork competitivo.

#### Lo que el programa **no** es

Para que no haya malentendidos: ser Founding Partner no implica co-propiedad, exclusividad, voto vinculante sobre el core ni descuento perpetuo. Es un acuerdo de "primera ola", generoso y con fecha, pensado para que arrancar contigo merezca la pena —no es una concesión sobre el proyecto.

El programa contempla **un máximo de 5 Founding Partners por país** (no 5 en total a nivel mundial). Cada país en el que entre DentalPin opera su propia cohorte de Founding Partners, con sus propias plazas, fecha de apertura y mapa de categorías. No hay prisa por llenarlas: las plazas son pocas a propósito, porque queremos elegir bien con quién arrancamos esto en cada mercado. Dentro de un mismo país, cada plaza se reserva para una categoría distinta del ecosistema (agenda automatizada, comunicación con paciente, IA clínica, integraciones de laboratorio, etc.); no se concede más de una plaza por categoría y país.

---

### 6. Compromisos de Dentaltix con sus colaboradores

Esto no va en una sola dirección. Si te pedimos calidad, soporte y buena fe, lo justo es que tú sepas exactamente qué puedes esperar de nosotros:

- **APIs estables.** Versionado semántico, ventana mínima de deprecación de 12 meses, changelog público.
- **Comunicación temprana.** Cambios estructurales en core, modelo de marketplace o políticas de la SaaS se comunican con antelación razonable a colaboradores activos. Para Founding Partners y Strategic, antes que al público general.
- **No canibalización oportunista.** Si Dentaltix decide construir un módulo oficial en una categoría donde ya existe un módulo Strategic o Founding Partner activo y conforme con esta política, lo notificará con un mínimo de **6 meses de antelación** y mantendrá un periodo razonable de coexistencia. El módulo de Dentaltix usará exactamente las mismas APIs que cualquier tercero, sin atajos privilegiados.
- **Pagos puntuales.** Liquidaciones del marketplace en los plazos publicados, con desglose claro y trazabilidad.
- **Defensa pública de la neutralidad.** Dentaltix asume la responsabilidad de mantener visible la neutralidad del ecosistema y de actuar cuando un actor —incluida ella misma— intente quebrarla.
- **Reconocimiento de la apuesta inicial.** Quienes apuesten por el proyecto en su fase temprana mantendrán el reconocimiento de Founding Partner mientras cumplan los compromisos básicos, también cuando lleguen jugadores más grandes.
- **Sin sorpresas legales.** Esta política no se modifica retroactivamente en perjuicio de acuerdos firmados con Founding Partners durante la vigencia de su acuerdo (ver §12).

Estos compromisos no se quedan en un PDF: aparecen también, por escrito, en el acuerdo que firmamos contigo.

---

### 7. Lo que no podemos ofrecerte (y por qué te conviene)

Con el mismo cariño con el que te decimos sí a muchas cosas, hay otras a las que vamos a responder siempre con un "no". No es desconfianza ni rigidez: es lo que mantiene el ecosistema neutral y, sobre todo, lo que protege tu inversión en él frente a actores que vengan después.

- **Co-propiedad o co-gobernanza del core.** Ningún colaborador, por antiguo o estratégico que sea, obtiene voto vinculante sobre el core, derecho de veto, ni participación en su roadmap más allá de la voz pública en RFCs.
- **Exclusividad por categoría.** No se concede exclusividad funcional ni territorial. Si entras como módulo de automatización de agenda, otros pueden entrar también en automatización de agenda. Esa misma regla evita que otro te bloquee mañana a ti.
- **Cambios al core a medida.** El core no se modifica para favorecer un caso de negocio particular de un colaborador. Si una API no existe, se propone vía RFC y se evalúa por su valor general, no por quién la pide.
- **Forks favoritos.** No se reconoce, recomienda ni apoya ningún fork del core, salvo despliegues legítimos auto-hospedados por clínicas o partners técnicos.
- **Equity, IP o branding compartido.** Una colaboración técnica o comercial no genera derechos sobre Dentared Odontology Services S.L., sobre el código del core, ni sobre la marca DentalPin.
- **Acceso privilegiado a datos de clínicas.** Los datos clínicos son de las clínicas. Ningún colaborador accede a datos agregados o desagregados sin consentimiento explícito de la clínica titular.

> **Por qué estos límites también te protegen a ti.** Si hoy vendiéramos exclusividad o co-gobernanza al primero que llega, mañana te tocaría a ti negociar contra alguien con más músculo. La regla simétrica —la misma para todos— es la única que aguanta a largo plazo, y por eso es también la mejor garantía que podemos darte.

---

### 8. Niveles de colaboración

| Nivel | Para quién | Requisitos | Beneficios |
|-------|-----------|------------|------------|
| **Community** | Cualquier desarrollador u organización | Módulo publicable, cumple guía técnica y legal | Listado en marketplace, comisión estándar |
| **Verified** | Colaboradores con módulo en producción y soporte demostrable | Revisión técnica, SLA mínimo, política de soporte pública | Badge "Verified", placement mejorado, co-marketing puntual |
| **Strategic** | Colaboradores en categorías clave o con tracción significativa | Acuerdo escrito, compromisos de calidad y soporte reforzados | Trato prioritario en RFCs, co-marketing, aviso anticipado de cambios estructurales |
| **Founding Partner** | Primeros colaboradores en la fase inicial del proyecto | Acuerdo escrito; ver §5 | Beneficios completos del programa Founding Partners |

El paso entre niveles es discrecional de Dentaltix y se basa en criterios objetivos publicados (calidad, soporte, adopción, alineamiento con esta política). El nivel Founding Partner es un programa cerrado en el tiempo; los demás permanecen abiertos.

---

### 9. Compromisos del colaborador

Por su parte, quien publique un módulo o integración en el ecosistema DentalPin asume estos compromisos —que son los mismos que tú esperarías de cualquier proveedor que entra en una clínica:

1. **Calidad técnica.** Cumplir la guía de creación de módulos (`docs/technical/creating-modules.md`), pasar revisión y tests.
2. **Soporte.** Publicar canal y SLA. Mantener el módulo compatible con las versiones de DentalPin soportadas.
3. **Cumplimiento legal.** Respeto a RGPD y normativa aplicable de datos clínicos en cada jurisdicción donde opere. Encargado de tratamiento debidamente formalizado cuando proceda.
4. **Transparencia con la clínica.** Pricing claro, condiciones de cancelación claras, exportación de datos del módulo siempre disponible para la clínica.
5. **No fork hostil.** No promover, distribuir ni recomendar forks competitivos del core mientras se forme parte del ecosistema oficial.
6. **Uso correcto de la marca.** Seguir las guías de marca y co-branding publicadas por Dentaltix.
7. **Conflictos de interés.** Declarar cualquier interés relevante (participación cruzada, acuerdos de exclusividad con terceros, etc.) que pueda afectar a la neutralidad del ecosistema.

Si algo se rompe, primero hablamos. Solo si el problema no se puede arreglar —o no se quiere arreglar— llegaríamos a suspender un módulo del marketplace o a retirar a un colaborador del programa. Siempre con plazo de remediación cuando el problema sea subsanable, y siempre por escrito.

---

### 10. Económico (resumen de alto nivel)

- **Core SaaS gratuito** para clínicas. Coste cubierto por el margen del marketplace y por servicios premium operados por Dentaltix (hosting dedicado, soporte, cumplimiento avanzado, etc.).
- **Módulos de terceros**: precio fijado por el colaborador. Dentaltix actúa como procesador de pagos y aplica una comisión estándar, idéntica para todos los colaboradores del mismo nivel. Mientras no exista un portal público de partners, las cifras concretas se acuerdan por escrito en cada contrato de marketplace; cuando exista el portal, se publicarán en abierto.
- **Para qué sirve esa comisión.** No es margen oportunista: financia el desarrollo y mantenimiento continuo del core, la infraestructura del SaaS oficial gratuito para clínicas, el procesamiento de pagos del marketplace y el soporte de primera línea. Sin esa comisión, ni el core abierto ni la SaaS gratuita serían sostenibles a largo plazo.
- **Founding Partners**: comisión 0% durante los **18 primeros meses** desde la activación de su módulo en el marketplace, y **50% de descuento sobre la comisión estándar a partir del mes 19**, de forma indefinida, mientras el módulo siga activo y el colaborador siga cumpliendo los compromisos del programa. El programa admite un **máximo de 5 Founding Partners por país**, no 5 a nivel mundial.
- **Liquidaciones**: ciclo y condiciones publicados en el acuerdo de marketplace.

Las cifras concretas pueden actualizarse con preaviso razonable, y cualquier cambio se aplica de forma uniforme a todos los colaboradores del mismo nivel. Hoy viven en los acuerdos individuales; cuando haya portal público de partners, se publicarán abiertamente allí.

---

### 11. Proceso de incorporación

1. **Contacto inicial** escribiendo a **ramon.martinez@dentaltix.com**. En esta fase inicial del proyecto, no hay todavía formulario ni portal: todas las conversaciones de partners las llevo personalmente yo, Ramón, fundador de Dentaltix.
2. **Conversación de encaje**: caso de uso, categoría, modelo de negocio, alineamiento con esta política.
3. **Acuerdo escrito**: contrato de marketplace y, si aplica, addendum de Founding Partner o Strategic.
4. **Desarrollo** del módulo siguiendo la guía técnica.
5. **Revisión técnica y legal** por parte de Dentaltix.
6. **Publicación** en el marketplace.
7. **Operación continua**: métricas, soporte, renovación.

Habrá casos en los que no encajemos, y cuando sea así te lo diremos en abierto y con motivos: cuando una incorporación entre en conflicto con esta política, con la neutralidad del ecosistema o con los intereses de las clínicas usuarias.

---

### 12. Cambios a esta política

Esta política irá evolucionando con el proyecto —sería raro que no lo hiciera. Cuando la cambiemos:

- Se publican con número de versión y changelog.
- Se notifican a colaboradores activos con un preaviso razonable.
- **No se aplican retroactivamente en perjuicio de acuerdos firmados con Founding Partners o Strategic durante la vigencia de su acuerdo.**

La política vigente siempre es la publicada en este archivo del repositorio oficial.

---

### 13. Contacto

DentalPin está en una fase muy temprana, así que de momento el canal es directo y personal: **ramon.martinez@dentaltix.com**. Soy Ramón, fundador de Dentaltix, y llevo personalmente cada conversación con colaboradores. Cuando el equipo y la adopción crezcan, abriremos canales dedicados (`partners@`, `brand@`, portal de partners) y lo anunciaremos aquí.

- ¿Quieres explorar una colaboración? Escríbeme y nos sentamos lo antes posible a ver si tiene sentido.
- ¿Asuntos de marca o uso de logotipo? Mismo email, indícalo en el asunto.
- ¿Algo de esta política no te queda claro o te chirría? Puedes abrir un issue público en el repositorio etiquetado `governance` —preferimos discutir estas cosas en abierto— o escribirme directamente.

---

*DentalPin pertenece a las clínicas que lo usan, a los desarrolladores que contribuyen y al ecosistema dental que lo adopta. Dentaltix es el guardián que se asegura de que ese reparto siga siendo justo —y eso incluye proteger la apuesta de quien colabora desde el principio.*
