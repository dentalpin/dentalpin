---
module: patients
last_verified_commit: 0e9a0ac
---

# Patients

The patients module manages identity records for the people your clinic
treats: name, contact details, demographics, and lifecycle status.
Almost every other module in DentalPin links back to a patient row.

## Screens

- [Patient list](./screens/list.md) — search, browse, create patients.
- [Patient detail](./screens/detail.md) — single patient view: identity
  card, extended demographics, sibling-module actions (recalls, photos,
  treatment plans, …).

## Quick reference

| Action | Required permission |
|--------|---------------------|
| Browse patients | `patients.read` |
| Create or edit a patient | `patients.write` |
| Archive a patient (soft delete) | `patients.write` |

Patients are never hard-deleted. Archived rows stay in the database for
audit and historical reporting; they're hidden from the default list and
search results.

## Related modules

- **Recalls** — sets the next contact date for a patient. Activates the
  "Set recall" button on the patient detail.
- **Treatment plans** — link plans and budgets to a patient.
- **Media / photos** — attach files and clinical photography to a
  patient (or to entities that belong to a patient).
- **Schedules** — book appointments against a patient.

For end-user instructions, follow the screen-by-screen guides above.

## Importing from CSV

`POST /api/v1/patients/import.csv` (multipart `file`, `patients.write`):

```bash
curl -X POST "https://clinic/api/v1/patients/import.csv?dry_run=false" \
  -H "Authorization: Bearer $TOKEN" -F file=@patients.csv
```

Columns: `first_name*`, `last_name*`, `phone`, `email`,
`date_of_birth` (YYYY-MM-DD or DD/MM/YYYY), `notes`,
`do_not_contact`, `national_id`, `national_id_type`,
`billing_name`, `billing_tax_id`. Delimiter `,` or `;`
(auto-detected), UTF-8, max 1000 rows / 1 MiB. Dry-run (default)
validates only and returns per-row errors plus `duplicates` (rows
matching an existing patient by national id, else email + birth
date; rows repeating within the file report `matched_on:
"same_file"` with a null `patient_id`); commit skips duplicates
unless `allow_duplicates=true`.
The report shape is `{total, valid, created, skipped, errors,
duplicates}`.
