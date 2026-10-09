# 0039 — pay_0004 duplicate earned-row deletion is accepted

- **Status:** accepted
- **Date:** 2026-10-05
- **Deciders:** maintainers
- **Tags:** migrations, payments, data-safety

## Context

`backend/app/modules/payments/migrations/versions/pay_0004_null_session_dedup.py:39-61`
DELETEs duplicate `patient_earned_entries` rows (two statements, no
archival) to enforce the per-session idempotency the release needs. The
downgrade cannot restore them. Issue #549 asked for a decision record:
document as accepted, or archive-then-delete.

## Decision

Accepted as-is. The deleted rows are the double-charge bug's output,
removed in the two steps `pay_0004`'s own docstring describes: step 1
deletes the NULL-session full-price row where per-session rows exist
for the same treatment (the double-booked full price, held under a
different session key and a different amount; the per-session rows are
the source of truth); step 2 dedupes multiple NULL-session rows per
treatment, keeping the earliest. This ran at the time of the migration
(2026-08-01) against a pre-production database with no live clinics.
Re-running the scenarios that created them reproduces nothing once the
idempotency guard exists.

## Consequences

### Good

- The earned ledger has a clean uniqueness invariant going forward.
- No archive-table machinery for rows that carry no information.

### Bad / accepted trade-offs

- If a production database ever carries such duplicates, this migration
  destroys them. Any future dedup migration on money-adjacent rows must
  archive-then-delete instead; cite this ADR as the counter-example.

## Alternatives considered

- **Archive-then-delete** - rejected: archive tables for information-free
  duplicates add schema nobody will ever read, for a pre-prod database.

## How to verify the rule still holds

- `grep -rn "DELETE FROM" backend/app/modules/payments/migrations/versions/`
  must show only this revision; new money-adjacent dedups need the
  archive shape.

## References

- `backend/app/modules/payments/migrations/versions/pay_0004_null_session_dedup.py:39-61`
- Issue #549
