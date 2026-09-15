---
module: prescriptions
screen: prescriptions
route: /prescriptions
last_verified_commit: HEAD
related_endpoints:
  - GET /api/v1/prescriptions/patients/{patient_id}/prescriptions
  - POST /api/v1/prescriptions/patients/{patient_id}/prescriptions
  - PATCH /api/v1/prescriptions/prescriptions/{prescription_id}
  - POST /api/v1/prescriptions/prescriptions/{prescription_id}/issue
  - POST /api/v1/prescriptions/prescriptions/{prescription_id}/cancel
  - GET /api/v1/prescriptions/prescriptions/{prescription_id}/pdf
related_permissions:
  - prescriptions.read
  - prescriptions.write
  - prescriptions.issue
related_paths:
  - backend/app/modules/prescriptions/frontend/pages/prescriptions/index.vue
---

# Prescriptions

Open with a patient selected to see their prescriptions, or start a
draft from the patient summary ("New prescription" action).

## What you can do

- **Draft** with free-text medication lines (or fill from a catalog
  entry / favorite template). Drafts edit freely.
- **Issue** freezes the prescription (prescriber snapshot attached);
  corrections are cancel + reissue, never edits.
- **Download** the PDF for printing. No email delivery in v1.
- Heed the allergy/interaction banner — it warns, never blocks.
