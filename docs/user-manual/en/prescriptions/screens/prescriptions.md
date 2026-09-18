---
module: prescriptions
screen: prescriptions
route: /prescriptions
last_verified_commit: c07d18a6d00fd5b4b17f801b64aa9bec0e31434a
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

- **Draft** with free-text medication lines (or from a favorite
  template). Drafts edit freely.
- **Issue** freezes the prescription (prescriber snapshot attached:
  name and license, no signature);
  corrections are cancel + reissue, never edits.
- **Download** the PDF for printing. No email delivery in v1.
  The PDF renders in the prescription's language and carries a
  DRAFT/CANCELLED mark when applicable.
- **Issue** and **Cancel** ask for confirmation (both are irreversible).
- Your **license number** lives in Settings (clinical section,
  prescriber identity) and prints on the PDF.
- Heed the allergy/interaction banner — it warns, never blocks.
