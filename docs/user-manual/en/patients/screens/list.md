---
module: patients
screen: list
route: /patients
related_endpoints:
  - GET /api/v1/patients
  - GET /api/v1/patients/recent
  - POST /api/v1/patients
related_permissions:
  - patients.read
  - patients.write
related_paths:
  - backend/app/modules/patients/router.py
  - backend/app/modules/patients/frontend/pages/patients/index.vue
last_verified_commit: f7c72c6f
screenshots:
  - patients.png
---

# Patient list

Lists every active patient in the clinic. From here you can search,
filter, open a patient's detail page, or create a new patient.

## At a glance

- **Default view:** active patients only. Archived patients are hidden;
  the list endpoint never returns them by default.
- **Status filter:** the chips pick exactly what you ask for. *Archived*
  on its own lists archived patients only; both chips lists both.
  Clearing the filter drops the restriction rather than falling back to
  active.
- **Recent panel:** the sidebar quick-access list shows the patients you
  opened most recently — backed by the `GET /api/v1/patients/recent`
  endpoint.
- **Pagination:** 20 patients per page. Use the page-size selector to
  raise it; the backend caps at 100.

## How to find a patient

1. Type a name, surname, or ID number into the search box at the top
   of the list. The query filters by exact and partial matches across
   identity fields.
2. Press **Enter** or wait for debounce — results refresh in place.
3. Click any row to open the
   [patient detail](./detail.md) screen.

## How to create a patient

> Requires the `patients.write` permission.

1. Click **New patient** in the top-right toolbar.
2. Fill in first and last name. Contact details, **identity document
   (NIF/NIE)** and date of birth are optional and can be completed
   later from the patient detail page. The document is used as the
   invoice tax id unless separate billing data is set.
3. Click **Save**. The new patient appears at the top of the list and
   the system publishes a `patient.created` event so other modules
   (recalls, notifications, …) can react.

To add many patients at once, click **Import CSV** next to it and
follow [Import from CSV](./import.md).

## Permissions

| You see / can do | Permission |
|------------------|-----------|
| Browse and search the list | `patients.read` |
| Open the **New patient** button | `patients.write` |
| See the **Import CSV** button | `patients.write` |

## Troubleshooting

- **The list is empty after a fresh install.** Run `./scripts/seed-demo.sh`
  to load demo data.
- **A patient I just created is missing.** Check the *Status* filter —
  if only *Archived* is selected, active rows are excluded.
