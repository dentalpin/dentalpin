# TODOS — DentalPin

> The open standard for dental clinic management.

---

## 1. VISION AND PRINCIPLES

### What is DentalPin

DentalPin is open source dental clinic management software designed to be:

- **Modular** — Every feature is a self-contained module
- **API-First** — Everything is accessible via REST API
- **Multi-tenant** — Built for clinic isolation from day one
- **Extensible** — Third parties can build integrations and modules

### License: BSL 1.1

- **Free to use** for clinics (self-hosted or cloud)
- **Contributions** welcome and encouraged
- **Prohibited** to host as a competing commercial SaaS
- **Converts to Apache 2.0** after 4 years

---

## 2. PRIORITIES

### Priority Tags

| Tag | Meaning | Timeline |
|-----|---------|----------|
| 🔴 P0 | Blocks first clinic in production | Immediate |
| 🟠 P1 | Required for 10 clinics + legal compliance | 3-6 months |
| 🟡 P2 | Enables ecosystem growth | 6-12 months |
| 🟢 P3 | Advanced features, long term | 12-24 months |

### Critical Legal Deadlines (Spain)

| Deadline | Requirement | Impact |
|----------|-------------|--------|
| **January 2027** | Verifactu mandatory for companies | Without this, no Spanish SL can legally use the software |
| **July 2027** | Verifactu mandatory for freelancers | Full Spanish market coverage |

---

## 3. PLATFORM LAYERS

### 3.1 Core Platform (BSL 1.1)

What is **NOT** a module. The foundation everything else builds on.

| Component | Status | Description |
|-----------|--------|-------------|
| Plugin System | ✅ | Auto-discovery, dependency resolution |
| Auth + RBAC | ✅ | JWT, 5 roles, wildcard permissions |
| Event Bus | ✅ | Pub/sub for module communication |
| Multi-tenancy | ✅ | Clinic isolation, membership |
| REST API | ✅ | OpenAPI, versioned |

---

### 3.2 First-Party Modules (BSL 1.1)

Included by default. Functionality every clinic needs.

| Module | Status | Function |
|--------|--------|----------|
| `clinical` | ⚠️ Partial | Patients, appointments (basic) |
| `odontogram` | ✅ | Interactive FDI dental chart |
| `catalog` | ✅ | Treatment catalog with VAT types |
| `budgets` | ✅  P0 | Budgets/quotes + PDF |
| `billing` | ✅  P0 | Invoicing |
| `patient-record` | ⚠️ Partial | Phase 1 ✅, Phase 2 ⚠️ (documents), Phase 3-4 pending |
| `clinical-notes` | 🟠 P1 | Clinical evolution (SOAP) |
| `imaging` | 🟠 P1 | Clinical images and X-rays |
| `booking` | 🟠 P1 | Online booking |
| `communications` | 🟠 P1 | Reminders, notifications |

---

#### Complete Patient Record 🔴 P0

The current patient record is basic. Implementation divided into 4 phases:

---

##### Phase 1: Core Patient Data + Medical History + Alerts ✅

Extended `clinical` module with:
- Patient demographics (gender, national_id, profession, workplace, address)
- Emergency contact with legal guardian support
- Medical history JSONB (allergies, medications, systemic diseases, surgical history, special conditions)
- Patient alerts computed from medical history
- Patient timeline populated via event handlers
- Sidebar + tabs UI layout with quick info and alerts banner

---

##### Phase 2: Documents + File Storage ⚠️ Partial

**Scope:** New `media` module with storage abstraction. Patient documents functionality.

**Architecture Decisions:**
- Separate `media` module (reusable for images, X-rays, attachments)
- StorageBackend protocol: LocalStorage (shipped), S3 (`storage/s3.py`,
  shipped with `STORAGE_BACKEND=s3`)
- File metadata in DB, actual files in configured storage
- Document types: consent, id_scan, insurance, report, referral, other

**Backend Tasks:**

| Task | Status | Description |
|------|--------|-------------|
| Create media module | ✅ | BaseModule subclass with dependencies: ["clinical"] |
| StorageBackend protocol | ✅ | upload, download, delete, get_url methods |
| LocalStorage implementation | ✅ | Docker volume mount, path-based storage |
| Document model | ✅ | patient_id, document_type, filename, storage_path, mime_type, file_size, title, description, metadata (JSONB), uploaded_by |
| Upload endpoint | ✅ | POST /patients/{id}/documents with multipart form, validation (size, type) |
| List/Get/Delete endpoints | ✅ | Standard CRUD with permission checks |
| Download endpoint | ✅ | Streaming response with correct content-type |
| Permissions | ✅ | media.documents.read/write |
| File validation | ✅ | Max size (10MB default), allowed MIME types |
| Alembic migration | ✅ | `o5p6q7r8s9t0_add_documents_table.py` |

**Frontend Tasks:**

| Task | Status | Description |
|------|--------|-------------|
| useDocuments composable | ✅ | fetchDocuments, uploadDocument, downloadDocument, deleteDocument, updateDocument |
| DocumentUpload component | ✅ | Drag-drop zone, progress indicator, type selector |
| DocumentGallery component | ✅ | Grid view, type filter, pagination |
| DocumentCard component | ✅ | PDF/image icon, title, type badge, download/edit/delete actions |
| DocumentViewer component | 🔴 | PDF inline viewer, image lightbox (not implemented) |
| Add Documents tab to patient | ✅ | Separate Documents tab in patient detail |
| i18n translations | ✅ | Spanish and English complete |

**Document Types:**

| Type | Description | Icon |
|------|-------------|------|
| consent | Signed consent forms | file-signature |
| id_scan | DNI/NIE/Passport scan | id-card |
| insurance | Insurance card | shield |
| report | External medical reports | file-text |
| referral | Referral letters | file-output |
| other | Other documents | file |

**Storage Configuration:**

```python
# backend/app/config.py
STORAGE_BACKEND: str = "local"  # local | s3
STORAGE_LOCAL_PATH: str = "/app/storage"
STORAGE_S3_BUCKET: str = ""     # required when STORAGE_BACKEND=s3
STORAGE_S3_REGION: str = ""
STORAGE_S3_ENDPOINT_URL: str = ""   # MinIO / Wasabi / Cloudflare R2
STORAGE_S3_ACCESS_KEY_ID: str = ""  # empty -> standard AWS chain
STORAGE_S3_SECRET_ACCESS_KEY: str = ""
STORAGE_MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
STORAGE_ALLOWED_MIME_TYPES: str = "application/pdf,image/jpeg,image/png"
```

**Files Created/Modified:**
- `backend/app/modules/media/` — New module (models, router, schemas, service, storage)
- `backend/alembic/versions/o5p6q7r8s9t0_add_documents_table.py` — Migration
- `backend/tests/test_media.py` — Backend tests
- `frontend/app/components/media/` — DocumentCard, DocumentGallery, DocumentUpload
- `frontend/app/composables/useDocuments.ts` — Documents composable
- `frontend/app/config/permissions.ts` — Added documents permissions
- `frontend/i18n/locales/{en,es}.json` — Translations

---

##### Phase 3: Clinical Images Gallery 🟠 P1

**Scope:** Extend media module with clinical image organization and treatment linkage.

**Architecture Decisions:**
- ClinicalImage extends Document with category and treatment association
- Thumbnail generation on upload (pillow/PIL)
- Before/after pairing via paired_image_id
- Categories organized by clinical use

**Backend Tasks:**

| Task | Description |
|------|-------------|
| ClinicalImage model | Extends Document: image_category, associated_treatment_id (FK ToothTreatment), is_before_image, paired_image_id, thumbnail_path |
| Thumbnail service | Generate thumbnails on upload (300x300), store alongside original |
| Category endpoints | GET /patients/{id}/clinical-images?category=intraoral_frontal |
| Before/after pairing | Link images, create comparison metadata |
| Treatment linkage | Associate images with specific tooth treatments |

**Frontend Tasks:**

| Task | Description |
|------|-------------|
| useClinicalImages composable | fetchImages, uploadImage, categorize, pair |
| ImageGallery component | Masonry grid, category tabs, date grouping |
| ImageViewer component | Lightbox with zoom, pan, navigation |
| ImageCompare component | Side-by-side slider for before/after |
| ImageUpload component | Category selector, treatment selector, before/after toggle |
| Add Images tab to patient | New tab in patient detail |

**Image Categories:**

| Category | Code | Description |
|----------|------|-------------|
| Intraoral Frontal | intraoral_frontal | Front view of teeth closed |
| Intraoral Left | intraoral_left | Left lateral view |
| Intraoral Right | intraoral_right | Right lateral view |
| Intraoral Occlusal Upper | intraoral_occlusal_upper | Mirror view upper arch |
| Intraoral Occlusal Lower | intraoral_occlusal_lower | Mirror view lower arch |
| Extraoral Frontal | extraoral_frontal | Face front view |
| Extraoral Smile | extraoral_smile | Smile view |
| Extraoral Profile Left | extraoral_profile_left | Left profile |
| Extraoral Profile Right | extraoral_profile_right | Right profile |
| Treatment Specific | treatment_specific | Associated with specific treatment |

---

##### Phase 4: X-rays and DICOM Foundation 🟡 P2

**Scope:** X-ray image support with DICOM awareness (no full viewer in this phase).

**Architecture Decisions:**
- Xray model extends ClinicalImage with radiography-specific fields
- DICOM metadata extraction (pydicom library)
- Convert DICOM to web-viewable format (JPEG preview)
- Store original DICOM for future viewer integration
- Temporal comparison via date slider

**Backend Tasks:**

| Task | Description |
|------|-------------|
| Xray model | Extends ClinicalImage: xray_type, tooth_numbers[], acquisition_date, dicom_metadata (JSONB), is_dicom |
| DICOM service | Extract metadata (study date, modality, patient info), convert to JPEG preview |
| Temporal comparison endpoint | GET /patients/{id}/xrays/compare?tooth=11&dates=2024-01,2025-01 |
| X-ray type classification | panoramic, periapical, bite_wing, cbct, cephalometric |

**Frontend Tasks:**

| Task | Description |
|------|-------------|
| useXrays composable | fetchXrays, uploadXray, compare |
| XrayGallery component | Grid with type filter, tooth filter |
| XrayViewer component | Zoom, contrast adjustment, measurement tools (basic) |
| XrayCompare component | Temporal slider, side-by-side, overlay |
| XrayUpload component | Type selector, tooth selector, date picker |
| Add X-rays section to Images tab | Sub-tab or separate section |

**X-ray Types:**

| Type | Code | Description |
|------|------|-------------|
| Panoramic | panoramic | Full mouth panoramic |
| Periapical | periapical | Single tooth detailed view |
| Bite Wing | bite_wing | Interproximal view |
| CBCT | cbct | 3D cone beam (metadata only, no 3D viewer) |
| Cephalometric | cephalometric | Lateral skull view |

**DICOM Metadata to Extract:**

| Tag | Field | Use |
|-----|-------|-----|
| (0008,0020) | Study Date | acquisition_date |
| (0008,0060) | Modality | xray_type hint |
| (0010,0010) | Patient Name | validation |
| (0018,0015) | Body Part | classification |
| (0028,0010) | Rows | image dimensions |
| (0028,0011) | Columns | image dimensions |

**Future Integration Points (not in Phase 4):**
- OHIF Viewer integration for CBCT
- cornerstone.js for web DICOM viewing
- AI-assisted pathology detection
- Measurement and annotation persistence

---

#### Treatment Catalog (`catalog`) ✅ Implemented

| Feature | Status | Description |
|---------|--------|-------------|
| Internal codes | ✅ | Per-clinic internal treatment codes |
| Multi-language | ✅ | Localized names and descriptions (i18n) |
| Categories | ✅ | Hierarchical categories with icons |
| Pricing | ✅ | Default price + cost price tracking |
| Duration | ✅ | Default times for scheduling integration |
| VAT | ✅ | Configurable VAT types per clinic |
| Odontogram mapping | ✅ | Link treatments to odontogram visualization |
| Treatment scope | ✅ | Surface vs whole tooth classification |
| Multi-code | 🟠 P1 | Official nomenclatures (RCOE, CCAM, CDT/ADA) |
| Price lists | 🟠 P1 | Multiple rates (private, insured, promotional) |
| Packages | 🟡 P2 | Combined treatment templates |
| Materials | 🟠 P1 | Inventory linkage |
| Import/Export | 🟠 P1 | CSV import/export |

---

#### Budgets (`budgets`) ✅ P0

| Feature | Description |
|---------|-------------|
| Linked lines | ✅ Catalog + tooth/surface from odontogram |
| Discounts |🔴 Per line and global |
| Workflow | ✅ Draft → Presented → Accepted → In progress → Completed |
| Partial acceptance | Patient accepts some lines | (Not for MVP, adds complexity)
| Validity | ✅ Expiration period |
| PDF | ✅ With clinic branding |
| Digital signature | 🔴 E-signature for acceptance |
| Conversion | 🔴 Budget → Appointments → Invoices |

---

#### Billing (`billing`) ✅ P0

| Feature | Description |
|---------|-------------|
| From budget | ✅ Auto-populate from budget |
| Manual | ✅ Direct creation |
| Status | ✅ Draft → Issued → Paid → Partial → Cancelled/Credit note |
| Multi-tax | ✅ VAT exempt (healthcare) vs taxable (cosmetic) |
| Payments | ✅ Record payments (cash, card, transfer) |
| Verifactu-ready | ✅ Fields prepared (hash, QR) |
| PDF |✅ With legal requirements |
| Series |🟠 Configurable numbering | (series need to be defined from the console. We need to do an UI to define series.)

---

### 3.3 Community/Third-Party Modules

Opportunities for developers, equipment manufacturers, labs, and insurers.

#### Compliance (by country)

| Module | Country | Description |
|--------|---------|-------------|
| `verifactu-es` | 🇪🇸 Spain | Hash chain, QR, AEAT submission |
| `factur-x-fr` | 🇫🇷 France | French electronic invoicing |
| `sdi-it` | 🇮🇹 Italy | Sistema di Interscambio |
| `furs-si` | 🇸🇮 Slovenia | FURS fiscalization |

#### Clinical Integrations

| Module | Type | Description |
|--------|------|-------------|
| `dicom-viewer` | Radiology | Embedded DICOM viewer |
| `lab-orders` | Labs | Orders to prosthetic labs |
| `insurance-claims` | Insurance | Claims processing |
| `intraoral-capture` | Hardware | Intraoral camera capture |

#### Communications

| Module | Description |
|--------|-------------|
| `sms-twilio` | Twilio SMS integration |
| `whatsapp-business` | WhatsApp Business API |
| `email-sendgrid` | SendGrid/Mailgun |

#### Clinical Specialties

| Module | Specialty | Description |
|--------|-----------|-------------|
| `ortho-tracking` | Orthodontics | Cephalometry, aligner tracking |
| `perio-charting` | Periodontics | Probing, PSR/BPE |
| `implant-planning` | Implantology | Planning, implant registry |
| `endo-workflow` | Endodontics | Working length, file sequence |

#### AI

| Module | Description |
|--------|-------------|
| `imaging-ai` | Assisted pathology detection in X-rays |
| `voice-dictation` | Clinical note dictation |
| `smart-scheduling` | ML-based schedule optimization |

---

## 4. OPPORTUNITIES FOR THIRD PARTIES

DentalPin is designed so the **entire dental industry** can build modules.

### For Dental Equipment Manufacturers

| Equipment Type | Example Manufacturers | Events to consume |
|----------------|----------------------|-------------------|
| Radiology/DICOM | Planmeca, Vatech, Carestream | `patient.opened`, `treatment.planned` |
| Intraoral cameras | Dentsply Sirona, Acteon | `appointment.started` |
| CAD/CAM | CEREC, 3Shape | `treatment.completed` |
| Chairs | KaVo, A-dec | `appointment.checked_in` |

**Benefit:** Your equipment integrates natively with the software clinics use 8h/day.

### For Prosthetic Labs

| Module | Function |
|--------|----------|
| `lab-orders` | Send cases from patient record |
| `lab-tracking` | Real-time work status |
| `digital-impressions` | STL file management |
| `shade-management` | Color communication |

**Benefit:** Direct order channel from clinical workflow.

### For Insurance Companies

| Module | Function |
|--------|----------|
| `insurance-coverage` | Automatic pre-authorizations |
| `insurance-billing` | Direct billing to insurer |
| `coverage-calculator` | Coverage simulation in budget |
| `claims-status` | Real-time claims tracking |

**Benefit:** Reduced friction in authorizations and payments.

### For Communication Companies

| Module | Function |
|--------|----------|
| `sms-reminders` | Twilio, MessageBird, Vonage |
| `whatsapp-business` | Bidirectional communication |
| `email-campaigns` | Recalls, dental marketing |
| `review-management` | Post-visit review requests |

### For Independent Developers

| Module | Complexity | Impact |
|--------|------------|--------|
| Translations (FR, PT, DE) | Low | High |
| Export ICS (Google Calendar) | Low | Medium |
| Dark mode | Low | Medium |
| Digital consents | Medium | High |
| Orthodontics tracking | High | Niche |
| Periodontics charting | High | Niche |

---

## 5. ROADMAP BY PHASE

### Phase 0: Foundation (Current) ✅

**What's already built:**

| Component | Status |
|-----------|--------|
| Backend FastAPI + SQLAlchemy | ✅ |
| Frontend Nuxt 3 + Nuxt UI | ✅ |
| Plugin system with auto-discovery | ✅ |
| RBAC with 5 roles and wildcards | ✅ |
| Multi-tenancy (clinic isolation) | ✅ |
| Event bus | ✅ |
| Clinical module (patients, appointments) | ✅ |
| Odontogram module (FDI chart) | ✅ |
| 6 frontend pages, 18 components | ✅ |
| Docker Compose deployment | ✅ |

---

### Phase 1: Functional Clinic MVP 🔴 P0

**Goal:** A small clinic can operate day to day.

| Module | Status | Key Deliverables |
|--------|--------|------------------|
| `patient-record` | 🔴 | Complete record: anamnesis, alerts, documents |
| `catalog` | ✅ | Treatment catalog with VAT types, odontogram mapping |
| `budgets` | ✅ | Budgets with complete workflow + PDF |
| `billing` | ✅ | Basic invoicing + PDF |
| `imaging-basic` | 🔴 | Basic clinical image gallery |
| AI Infrastructure | 🔴 | ToolRegistry, ContextProvider |

---

### Phase 2: Production 🟠 P1

**Goal:** Ready for 10 real clinics. Legal compliance.

| Module | Key Deliverables | Deadline |
|--------|------------------|----------|
| `verifactu-es` | Hash chain, QR, AEAT submission | **January 2027** |
| `booking` | Embeddable widget, standalone page | |
| `communications` | Reminders SMS/email/WhatsApp | |
| `inventory` | Stock management, reorder alerts | |
| `data-import` | Migration from Gesden, Clinic Cloud, CSV | |
| Multi-clinic | Clinic switcher, shared patients | |
| Payments | Stripe, Redsys integration | |

---

### Phase 3: Ecosystem 🟡 P2

**Goal:** Third parties build on the platform.

| Component | Key Deliverables |
|-----------|------------------|
| Marketplace v1 | Module browser, install/uninstall |
| Developer Portal | SDK, docs, module templates |
| Partner Program | Partner portal, certification |
| `insurance` | Coverage tables, claims |
| `clinical-notes` | SOAP evolution, templates |
| `prescriptions` | Prescriptions with interactions |
| AI Assistant | Chat interface, task execution |

---

### Phase 4: Scale 🟢 P3

**Goal:** DentalPin is the industry standard.

| Component | Key Deliverables |
|-----------|------------------|
| Specialty modules | Ortho, perio, implants, endo |
| International | FR, PT, DE, IT locales + compliance |
| AI Clinical | Decision support, imaging analysis |
| Voice | Dictation, voice commands |
| White-label | Theming for partners |

---

## 6. SUCCESS METRICS

### Adoption Metrics

| Milestone | Target | Validation |
|-----------|--------|------------|
| First clinic | Month 3 | 1 clinic using daily |
| Validation | Months 1-6 | 3-5 trusted clinics + feedback |
| Product-market fit | Month 6 | 20 clinics, churn <5% |
| Scale | Month 12 | 100 clinics |
| Standard | Month 24 | 1,000 clinics |

### Community Metrics

| Metric | Month 6 | Month 12 | Month 24 |
|--------|---------|----------|----------|
| GitHub Stars | 50 | 500 | 2,000 |
| External contributors | 3 | 10 | 50 |
| Third-party modules | 1 | 5 | 20 |
| Countries with deployments | 1 | 3 | 10 |

---

## 7. GOOD FIRST ISSUES

Small, well-scoped features for new contributors.

### Translations (no code)

- [ ] `i18n/locales/fr.json` — French translation
- [ ] `i18n/locales/pt.json` — Portuguese translation
- [ ] `i18n/locales/de.json` — German translation

### Frontend (low risk)

- [ ] Keyboard shortcuts for common actions
- [ ] Export appointment to ICS format (Google Calendar)
- [ ] Print view for patient record
- [ ] Skeleton loaders for all pages

### Backend (low risk)

- [ ] Improved seed data (more test cases)
- [ ] Detailed health check endpoint (`/health/detailed`)
- [ ] Configurable rate limiting

### Documentation

- [ ] Tutorial: "My first module in 30 minutes"
- [ ] Video walkthrough of architecture
- [ ] Updated architecture diagrams

### Testing

- [ ] E2E tests with Playwright for critical flows
- [ ] Increase unit test coverage to 80%
- [ ] Accessibility (a11y) tests

---

## 8. TECHNICAL DETAILS BY MODULE

### Verifactu (`verifactu-es`) 🟠 P1

**Legal deadline: January 2027 (companies), July 2027 (freelancers)**

| Component | Description |
|-----------|-------------|
| Hash chain | SHA-256 chained from previous invoice |
| QR code | Generation on each invoice |
| AEAT submission | Real-time or batched submission |
| Certificates | Digital signature management |
| Audit log | Immutable events for auditing |
| Separate module | Non-Spanish deployments don't load this |

**Extensible:** The pattern works for Factur-X (FR), SDI (IT), etc.

---

### Clinical Notes (`clinical-notes`) 🟠 P1

| Feature | Description |
|---------|-------------|
| Rich text | With attachments (images, files) |
| Templates | By treatment type (endo, implant, etc.) |
| Quick vs structured | Toggle by preference |
| Lock after sign | Not editable after finalization, only amendments |
| AI dictation | Voice-to-text + auto-structuring |
| Searchable | Full-text search across patients |

---

### Online Booking (`booking`) 🟠 P1

| Feature | Description |
|---------|-------------|
| Embeddable widget | For clinic website |
| Standalone page | With clinic branding |
| Configurable slots | By treatment type |
| New patient registration | During booking |
| ICS invite | Confirmation with calendar file |
| Anti-spam | Captcha, rate limiting |

---

### Data Import (`data-import`) 🟠 P1

**Critical:** Without migration, nobody switches software.

| Source | Format |
|--------|--------|
| Gesden | Specific export |
| Clinic Cloud | Specific export |
| CS R4 | Specific export |
| Generic | CSV/Excel mapping tool |
| FHIR | For interoperability |

| Feature | Description |
|---------|-------------|
| Mapping tool | Map source fields → DentalPin |
| Dry-run | Preview before commit |
| Validation | Detect errors and conflicts |
| Rollback | Ability to undo |

---

### AI Infrastructure 🔴 P0

Tracked in issue #42. Phase 1 landed the core contract; Phase 2/3 extend the system with UX, a reference agent, and scheduling.

**Phase 1 — Core Contract ✅ (shipped)**

| Component | Status | Description |
|-----------|--------|-------------|
| `ToolRegistry` | ✅ | Namespaced registry, JSON Schema helper, single-chokepoint `call()` |
| `BaseAgent` + `AgentContext` | ✅ | Abstract base, mode enum, execution context |
| `BaseModule.get_tools()` | ✅ | Mandatory abstract on every module (all 13 stubbed) |
| `BaseModule.get_agents()` | ✅ | Default `[]`, override to register agent classes |
| Guardrails | ✅ | Rate limits, blocked tools, require-approval patterns, auto-approval for DESTRUCTIVE / supervised-WRITE |
| Audit log | ✅ | `agent_audit_logs` table, every tool attempt recorded |
| Approval queue (backend) | ✅ | `agent_approval_queue` + service + endpoints |
| `agents.*` RBAC | ✅ | `agents.view/supervise/configure/manage` permissions |
| Docs | ✅ | `docs/technical/creating-modules.md` §12 "AI agent integration" |

**Phase 2 — UX + First Agent 🟠 P1**

- [ ] **Frontend approval UI** — `/approvals` page, pending-count badge in navbar, approve/reject modal with notes field. Use `ListRow` + `StatusBadge`.
- [ ] **Reference Appointment Reminder Agent** — standalone module at `backend/app/modules/agents/reminder/`. Add `anthropic` SDK to `backend/requirements.txt`. Demonstrates tool discovery, multi-turn tool loop, audit trail.
- [ ] **Cron / scheduling trigger** — APScheduler in-process or external cron hitting `POST /api/v1/agents/{id}/run`. Decide when building the reminder agent.
- [ ] **Per-module tool retrofit** — wrap existing service methods as Tools, module by module, as real agents need them. Start with `agenda` (appointments) + `patients` (search) since the reminder agent needs them.

**Phase 3 — Hardening 🟡 P2**

- [ ] Per-clinic guardrail configuration UI (admin) — edit rate limits, blocked patterns, require-approval patterns from settings
- [ ] `AgentMemory` production backends — Redis for short-term session memory, Postgres for long-term
- [ ] LLM abstraction layer — optional, only if a second provider appears or cost tracking needs a central chokepoint
- [ ] Distributed rate-limit store — replace in-process counters once DentalPin runs with multiple backend workers
- [ ] Token / cost metering per clinic — billing dashboard

**Non-goals (deferred indefinitely)**

- LLM provider abstraction in core — each agent imports its own SDK
- Multi-agent coordination — agents communicate via the existing event bus, not a custom protocol
- Vector DB / RAG primitives — add only when a concrete agent requires them

---

## 9. COMPLIANCE & SECURITY

### GDPR 🟠 P1

| Feature | Description |
|---------|-------------|
| Consent management | Consent tracking by channel |
| Right of access | Patient data export |
| Right to erasure | Anonymization/deletion workflow |
| Data minimization | Configurable retention periods |
| Breach notification | Notification workflow |

### Audit Log 🔴 P0

| Feature | Description |
|---------|-------------|
| Immutable | Append-only, no tampering |
| Complete | Who, what, when, where, before/after |
| Searchable | Filterable by user, entity, date |
| Exportable | For external audits |
| Retention | Configurable policies |

### Backup & DR 🟠 P1

| Feature | Description |
|---------|-------------|
| Automated daily | Database + files |
| Point-in-time | WAL-based recovery |
| Cross-region | Optional replication |
| One-click restore | Easy recovery |
| Encryption | At rest |

---

## 10. MODULE ARCHITECTURE

### Module Anatomy

```python
# backend/app/modules/mymodule/__init__.py
class MyModule(BaseModule):
    @property
    def name(self) -> str:
        return "mymodule"  # Router at /api/v1/mymodule/

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def dependencies(self) -> list[str]:
        return ["clinical"]  # Loaded after clinical

    def get_models(self) -> list:
        return [MyModel]

    def get_router(self) -> APIRouter:
        return router

    def get_permissions(self) -> list[str]:
        return ["resource.read", "resource.write"]

    def get_event_handlers(self) -> dict:
        return {"patient.created": self._on_patient_created}

    def get_ai_tools(self) -> list:  # AI-native
        return [CreateResourceTool(), ListResourcesTool()]
```

### Event Bus

```python
# Publishing
from app.core.events import event_bus
event_bus.publish("patient.created", {"patient_id": str(patient.id)})

# Subscribing
def get_event_handlers(self) -> dict:
    return {"patient.created": self._handle}
```

### Frontend Extension Points

| Extension Point | Use |
|-----------------|-----|
| Navigation | Register menu items |
| Patient tabs | Add tabs to patient record |
| Dashboard widgets | Cards on main dashboard |
| Action buttons | Contextual buttons |
| Settings pages | Configuration pages |

---

## 11. EXECUTIVE SUMMARY

### What is DentalPin

Open source dental clinic management software:
- **Free core** generates adoption and ecosystem
- **Modular architecture** enables third-party integrations
- **BSL 1.1 license** protects against SaaS competitors while allowing free use

### Why it exists

1. The dental software market is fragmented and legacy
2. Clinics deserve modern, open, affordable software
3. An open standard benefits the entire industry

### What to build first

1. 🔴 **Complete patient record** — Without this, no MVP
2. ✅ **Catalog** — Treatment catalog implemented
3. 🔴 **Budgets + Billing** — The revenue workflow (depends on catalog ✅)
4. 🟠 **Verifactu** — Mandatory legal compliance
5. 🟠 **Inventory** — Stock and supplies management

### How we measure success

**Primary metric:** Active clinics using DentalPin daily.

Everything else (stars, contributors, modules) are supporting indicators.
