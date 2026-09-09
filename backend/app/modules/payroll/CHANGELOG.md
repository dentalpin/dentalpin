# Changelog - payroll module

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Draft delete actions (follow-up to #390, now merged): remove-entry
  and delete-empty-period buttons with confirmation on the entries and
  periods pages; 409s render as error toasts.
- Admin-only frontend layer (issue #391): profiles, periods,
  period-detail entries and reports pages under `/payroll/*`, backend-
  driven nav (manifest `frontend.navigation`), `PERMISSIONS.payroll.*`
  mirror, 10 layer locales, user-manual screens en/es. Profile form
  defaults to the clinic currency. Entry/period
  remove actions wait for #399 (draft deletes) to merge.
- Draft corrections (issue #390): `DELETE /entries/{id}` and
  `DELETE /periods/{id}` (204, `payroll.write`) — entries delete while
  their period is draft (409 after close); periods delete while draft
  AND empty (409 otherwise). Closed/paid records stay immutable.
- Initial module (roadmap issue #229, approved v1): staff payroll with
  encrypted bank/tax data, monthly periods, raw entries, reports.
- 3 tables on own Alembic branch (`payr_0001`, no `depends_on`):
  `payroll_profiles` (Fernet-encrypted bank/tax, unique per
  clinic+user), `payroll_periods` (`YYYY-MM`, draft/closed/paid),
  `payroll_entries` (gross/deductions/net stored as entered, unique per
  period+user).
- Plaintext boundary: write-only secrets, masked responses (`last_4` +
  `has_*`), masked event payloads, no agent tools.
- RBAC: `payroll.read/write`, `payroll.reports.read`, admin-only.
  Profiles/entries only accept users with a membership in the clinic.
- Events `payroll.profile.updated`, `payroll.period.status_changed`.
