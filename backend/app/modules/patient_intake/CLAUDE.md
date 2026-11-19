# Patient intake

Optional backend for versioned first-visit forms and staff review.

- Scope all reads and mutations by clinic. Reception reviews contact, identity
  and preferences. Clinical review uses the existing medical permissions.
- Call `record_signed_submission` only after trusted signing. Keep public
  token handling, signature and evidence in the follow-up that reuses #906.
- Lock the patient before applying a review or changing consent. The GDPR
  ledger, provenance, verified preferences and pending cancellation share a
  transaction. The medical update event carries IDs and a generic summary.
- `pint_0001` uses the module branch. The module cannot be uninstalled through
  the application because it owns retained submissions and consent provenance.
- Read the [workflow and retention settings](../../../../docs/technical/patient_intake/overview.md)
  and the [staff endpoint permissions](../../../../docs/technical/patient_intake/permissions.md) when changing the contract.
