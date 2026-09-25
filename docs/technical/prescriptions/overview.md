# prescriptions — overview

Country-agnostic clinical prescription pad (issue #269). Drafts with
free-text medication lines (catalog autofill when `medication_catalog`
is installed), issue/cancel lifecycle with frozen prescriber snapshot,
favorite-combo templates, allergy/interaction safety banner, and PDF
download/print.

Legal/format requirements per country ship as localization modules on
top (same pattern as billing → verifactu): they implement
`PrescriptionComplianceHook` and register for their `country_code`.
No email delivery in v1.
