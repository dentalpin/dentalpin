---
module: payroll
last_verified_commit: 0f333000
---

# payroll — overview

Staff payroll with encrypted bank/tax data (issue #229). Admin-only
compliance module: per-staff profiles, monthly periods with a status
lifecycle, raw per-employee entries, and pure-aggregation reports.
No tax computation and no country rules in v1; no agent tools — the
agent layer never sees payroll.

## What it is

Admin-authenticated endpoints under `/api/v1/payroll/` (JWT +
`payroll.*` RBAC, admin role only). A clinic keeps one profile per
staff user (salary/hourly base, currency, encrypted bank account and
tax ID), opens one period per month (`YYYY-MM`), records raw entries
(gross/deductions/net as entered), and reads monthly/annual rollups.

Routes:

- `GET /api/v1/payroll/profiles` — list masked profiles
- `POST /api/v1/payroll/profiles` — create a profile (201)
- `GET /api/v1/payroll/profiles/{id}` — one masked profile
- `PATCH /api/v1/payroll/profiles/{id}` — edit terms / rotate secrets
- `GET /api/v1/payroll/periods` — list periods
- `POST /api/v1/payroll/periods` — open a draft period (201)
- `GET /api/v1/payroll/periods/{id}` — one period
- `POST /api/v1/payroll/periods/{id}/status` — draft → closed → paid
- `GET /api/v1/payroll/periods/{id}/entries` — entries of a period
- `POST /api/v1/payroll/entries` — raw entry (201, draft only)
- `GET /api/v1/payroll/entries/{id}` — one entry
- `PATCH /api/v1/payroll/entries/{id}` — edit a draft entry
- `GET /api/v1/payroll/reports/monthly?month=` — period rollup
- `GET /api/v1/payroll/reports/annual?year=` — year rollup

## Data model

Three tables, all `clinic_id`-scoped and indexed on `clinic_id`:

| Table | Purpose |
|---|---|
| `payroll_profiles` | profile + Fernet-encrypted bank/tax, unique per clinic+user |
| `payroll_periods` | month + status, unique per clinic+month |
| `payroll_entries` | gross/deductions/net as entered, unique per period+user |

Migration `payr_0001_initial` on own Alembic branch (`payroll`), no
`depends_on` (core-auth FKs need none).

## Service layer

- `ProfileService` — create (user must exist → 404; duplicate → 409),
  masked reads, replace-to-edit updates.
- `PeriodService` — strictly draft → closed → paid (409 on skips),
  publishes `payroll.period.status_changed`.
- `EntryService` — draft-period gate (409), `net == gross -
  deductions` validation (422), duplicate → 409.
- `ReportService` — monthly/annual sums in the clinic currency.

## Plaintext boundary

Bank/tax values are write-only: encrypted at the service boundary,
never logged, published, or serialized. Responses and events carry
`last_4` / `has_*` / ids only. Rotating `SECRET_KEY` requires
re-encrypting stored values (same trade-off as verifactu).

## Tenancy

Every query filters by `clinic_id`; users are global rows, so the
profile/entry scoping is what isolates clinics. Unknown users are a
404, cross-clinic ids are invisible (404, never 403).

## Constraints

Own Alembic branch (`payroll`); `manifest.depends = []`. No agent
tools. No hard deletes — profiles deactivate, periods/entries are
immutable records.

See [`./permissions.md`](./permissions.md) and [`./events.md`](./events.md)
for full detail.
