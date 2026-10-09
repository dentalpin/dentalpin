# 0040 — ag_0002 appointment status normalization is accepted

- **Status:** accepted
- **Date:** 2026-10-05
- **Deciders:** maintainers
- **Tags:** migrations, agenda, data-safety

## Context

`backend/app/modules/agenda/migrations/versions/ag_0002_status_lifecycle.py:104-112`
rewrites any appointment status outside the canonical set to `scheduled`
before adding the CHECK constraint ("defensive; no-op on clean installs").
On dirty installs carrying legacy statuses this is irreversible and silent.
Issue #550 asked to document as accepted, or back up affected rows first.

## Decision

Accepted as-is. Statuses outside the canonical set cannot be interpreted
by the state machine (the canonical map `VALID_TRANSITIONS` in
`backend/app/modules/agenda/service.py:35`, enforced by
`AppointmentService.transition` at `service.py:637-639`, which raises
`InvalidTransitionError` for any other value), so preserving them would
trade a loud, queryable migration for silent breakage later. The
rewrite itself is silent (one bulk `UPDATE`, no per-row logging), and
clean installs (the only supported fresh shape) are untouched.

## Consequences

### Good

- The CHECK constraint holds on every install, clean or dirty.
- No backup-table machinery for uninterpretable enum values.

### Bad / accepted trade-offs

- A dirty install loses the original non-canonical status strings.
  Operators upgrading with custom statuses should snapshot the
  `appointments` table first; a future normalization on user-authored
  data (names, notes) must back up first instead.

## Alternatives considered

- **Back up affected rows first** - rejected: the values being
  overwritten are by definition uninterpretable by the app, so a backup
  table preserves bytes nobody can act on. Kept as the rule for
  user-authored data (see above).

## How to verify the rule still holds

- New status-normalizing migrations must either be no-ops on dirty data
  or carry a backup; cite this ADR when reviewing them.

## References

- `backend/app/modules/agenda/migrations/versions/ag_0002_status_lifecycle.py:104-112`
- Issue #550
