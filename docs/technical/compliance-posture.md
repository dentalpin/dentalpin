# Compliance posture — patient data, DICOM metadata, AI processing

> Cross-cutting posture statement for operators and reviewers. It describes
> how DentalPin handles regulated data **today** and what an operator must do
> to stay compliant. It is not legal advice and not a certification.
> Sections marked *planned* bind future modules (§§3–4); everything else
> describes shipped behavior.
>
> Normative references: EU 2016/679 (GDPR) via the `gdpr` module (PR #374);
> HIPAA-style safeguards where they map to our controls. No HIPAA
> certification is claimed.

## 1. Data map (what regulated data exists and where)

| Category | Lives in | Notes |
|---|---|---|
| Patient identity + contact (name, phone, email, DNI) | `patients`, `contacts` | Core PII; every query scoped by `clinic_id` |
| Clinical records (charts, notes, plans, images) | `patients_clinical`, `clinical_notes`, `odontogram`, `treatment_plan`, `media`, `documents` | Health data (GDPR Art. 9 special category) |
| DICOM metadata (PatientID, PatientName, StudyInstanceUID, …) | planned `imaging_viewer.dicom_metadata` JSONB + raw bytes in `media`/`documents` (branch, not yet merged) | Identity leaks hide in tags — see §3 |
| Consents, DSRs, erasure audit, breach register | `gdpr` module tables | The accountability layer (§5) |
| AI job inputs/outputs (frames, overlays, transcripts) | planned `imaging_ai` job records + sidecar hosts (branch, not yet merged) | Never auto-finalized into records (§4) |
| Auth + access traces | core auth, `activity_journal` | Who touched what, when |
| Copilot prompts + tool results (today) | `copilot` module: redaction-gated cloud LLM path | See below — redaction gate, not a ban |

> **Copilot today (shipped, not planned).** The assistant backend runs
> through a redaction gate (`copilot/CLAUDE.md`, `copilot_settings.
> redaction_enabled`, default on): PII fields tokenize deterministically
> before any cloud call, and tools flagged `exposes_free_text` are
> excluded from the cloud path entirely. Tool calls re-check the
> caller's role permissions at the chokepoint; WRITE/DESTRUCTIVE tools
> need inline user confirmation. The posture below (§4) governs
> *planned imaging AI*; this paragraph governs the shipped copilot.

## 2. Tenancy and access control (the primary safeguard)

- **Every query filters by `clinic_id`** from `get_clinic_context` — including
  inside agent tool handlers. An id-only lookup is treated as a security bug
  (CI reviewer bar, L1).
- Endpoints require `require_permission("module.resource.action")`;
  permissions are module-prefixed and merged from manifests at runtime.
  Frontend references `PERMISSIONS.*` via `usePermissions()` — never raw strings.
- Cross-clinic ids resolve to 404, never an oracle (no existence disclosure).
- Patient data is **soft-deleted, never hard-deleted**; erasure means
  retention-gated blanking (Art. 17(3) — billing, legal claims), executed
  through the `gdpr` module so it is audited.

## 3. DICOM metadata and the RVG import path (planned modules)

> Binding rules, candidate for an ADR (decision pending).
> The `imaging_viewer` / `imaging_ai` branches are not merged yet. These
> rules bind the day they land; nothing below describes shipped behavior.

- DICOM tags routinely embed direct identifiers (PatientName, PatientID,
  birth dates). Treat extracted `dicom_metadata` as PII with the same
  protections as the patient row: `clinic_id` scoping, RBAC-gated proxy,
  no logging of tag values.
- The RVG watch-folder importer (T1) must: fingerprint files by content hash
  (dedup, no silent re-import), keep failed files discoverable with retry,
  suggest patient matches for human approval (never auto-link an
  unlinked identity on first sight), and store the DICOM-PatientID link
  explicitly so future files auto-import **only** through an approved link.
- De-identification for any secondary use (demos, exports, AI training data)
  is a deliberate operator action, not a default — tag-level blanking must
  cover PatientID/PatientName/other IDs, and the action is recorded.

## 4. AI processing boundaries (planned modules)

> Binding rules, candidate for an ADR (decision pending). Same
> status as §3: binding on the `imaging_ai` rebuild, not shipped.

- AI runs as **operator-provided sidecars** for imaging AI (nnU-Net,
  pano, OCR, transcription
  runners) behind the `imaging_ai` `Runner` protocol — never as in-process
  cloud calls from the backend. No patient data leaves the clinic network
  unless the operator configures a cloud backend.
- Cloud AI backends require a **recorded patient consent** (`gdpr` consents,
  purpose-scoped) before first use, plus a data-processing agreement with the
  provider. Defaults are on-prem; cloud is opt-in per clinic.
- AI outputs are **drafts**: overlays, OCR lines, transcripts attach as
  unconfirmed data for clinician review and are never auto-finalized into
  clinical records. Research-grade model output is never presented as
  diagnosis (Slicer-license §4 pattern).

## 5. Accountability layer (`gdpr` module)

- Data-subject requests (access, rectification, erasure, portability,
  restriction) with a 30-day SLA tracker; consent grant/withdraw with audit
  continuity; retention policies gating erasure eligibility; immutable
  erasure audit log; breach register (Art. 33–34: assess, record, notify
  authority within 72h where required, communicate to subjects where required).
- Portability export (`GET /gdpr/export/{patient_id}`) is the answering
  mechanism for access/portability DSRs and for CSV-style data-portability
  requests — machine-readable, clinic-scoped, permission-gated.

## 6. Operator duties (what the software cannot do for you)

1. Host hardening, encrypted backups, and access to the deployment itself.
2. Signing DPAs with any cloud AI provider before enabling cloud backends.
3. Training staff on the approval queue (RVG matching), consent capture, and
   breach reporting within 72 hours.
4. Reviewing retention policies yearly; keeping `legal_hold_until` current.
5. Re-verifying this posture after every imaging/AI track ships (T1–T6).

## 7. Explicitly not claimed

HIPAA certification; automatic anonymization; cross-border transfer
mechanisms beyond what the operator configures; legal review of
retention periods (those are jurisdictional and the operator's counsel
sets them).
