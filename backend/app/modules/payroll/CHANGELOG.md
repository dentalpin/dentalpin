# Changelog - payroll module

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Initial module (roadmap issue #229, approved v1): staff payroll with
  encrypted bank/tax data, monthly periods, raw entries, reports.
- 3 tables on own Alembic branch (`pay_0001`, no `depends_on`):
  `payroll_profiles` (Fernet-encrypted bank/tax, unique per
  clinic+user), `payroll_periods` (`YYYY-MM`, draft/closed/paid),
  `payroll_entries` (gross/deductions/net stored as entered, unique per
  period+user).
- Plaintext boundary: write-only secrets, masked responses (`last_4` +
  `has_*`), masked event payloads, no agent tools.
- RBAC: `payroll.read/write`, `payroll.reports.read`, admin-only.
- Events `payroll.profile.updated`, `payroll.period.status_changed`.
