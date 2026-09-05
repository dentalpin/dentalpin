# payroll module

Staff payroll with encrypted bank/tax data (issue #229, approved v1).
Admin-only compliance module: profiles, monthly periods, raw entries,
aggregation reports. No tax computation, no country rules, no agent
tools — the agent layer never sees payroll.

## What it does

Routes mounted at `/api/v1/payroll/` (all `payroll.*`-gated, admin only).

- `GET    /profiles`          — list profiles (masked); `payroll.read`
- `POST   /profiles`          — create a profile, encrypting bank/tax (201); `payroll.write`
- `GET    /profiles/{id}`     — single masked profile; `payroll.read`
- `PATCH  /profiles/{id}`     — edit terms; replace-to-edit secrets; `payroll.write`
- `GET    /periods`           — list periods; `payroll.read`
- `POST   /periods`           — open a `YYYY-MM` draft period (201); `payroll.write`
- `GET    /periods/{id}`      — single period; `payroll.read`
- `POST   /periods/{id}/status` — draft → closed → paid; `payroll.write`
- `GET    /periods/{id}/entries` — entries of a period; `payroll.read`
- `POST   /entries`           — raw entry (201, draft periods only); `payroll.write`
- `GET    /entries/{id}`      — single entry; `payroll.read`
- `PATCH  /entries/{id}`      — edit a draft entry; `payroll.write`
- `GET    /reports/monthly?month=` — period rollup; `payroll.reports.read`
- `GET    /reports/annual?year=`   — year rollup; `payroll.reports.read`

## Data model

3 tables, all `clinic_id`-scoped:

- `payroll_profiles` — `user_id` FK `users.id` (unique per clinic),
  `payment_type` (monthly | hourly), `base_amount`, `currency`,
  `bank_account_encrypted` + `tax_id_encrypted` (Fernet Text),
  `is_active`, `country_code` (forward-compat, unused in v1).
- `payroll_periods` — `month` (`YYYY-MM`, unique per clinic), `status`
  (draft | closed | paid).
- `payroll_entries` — `period_id` + `user_id` FKs, `gross`,
  `deductions`, `net` (stored as entered, validated
  `net == gross - deductions`), `notes`, unique per (period, user).

Migration `payr_0001_initial` on own Alembic branch (`payroll`), no
`depends_on` (core FKs need none — staff_tasks pattern).

## Plaintext boundary (security contract)

- Bank/tax arrive write-only on create/replace; `encrypt_password` at
  the service boundary; never logged, never published, never queried
  back except transiently for `last_4`.
- Responses (`mask_profile`) expose `has_bank_account`,
  `bank_last_4`, `has_tax_id`, `tax_last_4` only. A test asserts the
  masked shape on every touching response.
- Events carry ids only (`profile_id`, `user_id`, `period_id`, `month`,
  statuses) — no amounts, no secrets.
- `get_tools()` is intentionally absent (BaseModule default `[]`):
  no agent tool may touch payroll in v1.
- Rotating `SECRET_KEY` requires re-encrypting stored values (same
  trade-off as verifactu; per-tenant keys/KMS out of scope).

## Dependencies

`manifest.depends = []` — the only cross-boundary reads are core auth
(`User`, `Clinic.currency`), which is core, not a module.

## Permissions

`payroll.read`, `payroll.write`, `payroll.reports.read`. Granted to
`admin` (`*`) only — no other role sees payroll.

## Events published

| Event | When | Payload keys |
|---|---|---|
| `payroll.profile.updated` | profile created/updated | `clinic_id`, `profile_id`, `user_id` |
| `payroll.period.status_changed` | period transitions | `clinic_id`, `period_id`, `month`, `from_status`, `to_status` |

## Lifecycle

`installable=True`, `auto_install=False`, `removable=True` with
roundtrip uninstall test.

## Gotchas

- **Every query filters `clinic_id`.** Users are global rows; the
  profile/entry scoping is what isolates clinics.
- **Entries mutate only in draft periods** (409 otherwise); periods move
  strictly draft → closed → paid (409 on skips).
- **`net` is validated, not computed** — unbalanced books are a 422.
- **No hard deletes anywhere** — profiles deactivate via `is_active`;
  periods/entries are immutable records (L7).

## CHANGELOG

See `./CHANGELOG.md`.
