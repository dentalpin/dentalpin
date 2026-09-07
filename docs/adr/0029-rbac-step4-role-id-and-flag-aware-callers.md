# 0029 — RBAC step 4: role_id writes and flag-aware permission callers

- **Status:** proposed
- **Date:** 2026-09-07
- **Deciders:** maintainer (sign-off requested in issue #46)
- **Tags:** security, multi-tenancy, core

## Context

ADR 0024 shipped DB-backed RBAC behind `RBAC_FROM_DB` (default off) with
two explicit follow-ups: `clinic_memberships.role_id` was written only by
the migration backfill, and the synchronous `has_permission(ctx.role, ...)`
callers in schedules / verifactu / copilot / plugins kept resolving through
the static map, so custom roles and per-clinic overrides were ignored on
those paths once the flag flips. The maintainer's review of #400 names both
as step 4 of issue #46, gating the drop of the static map.

## Decision

Every membership write path persists the `roles`-row FK alongside the role
string (setup register, create-user, update-user, migration-import mappers),
and every non-`require_permission` caller resolves through two flag-aware
core helpers in `app/core/auth/rbac.py`: `granted_permissions_for`
(grant sets for agent contexts, nudges, nav filtering) and
`has_permission_for` (single checks in schedules, verifactu, copilot
history). `require_permission` and `/me` route through the same helpers, so
the eventual flag removal is a one-line change. The flag itself and the
static map stay until the maintainer signs off the always-DB flip (asked in
issue #46); the string `role` column stays as the flag-off read path.

## Consequences

### Good

- Custom roles and overrides take effect on every backend path under the
  flag: professional-schedule gates, the verifactu promote check, copilot
  history scoping, nudge visibility, agent tool chokepoints, and sidebar
  nav filtering.
- Role deletion cannot strand FK-held memberships: the 409 guard checks
  `role_id` as well as the role string.
- No route-signature churn: the schedules gate and nav filter keep their
  shapes; DB resolution is one cached round-trip per request at most.

### Bad / accepted trade-offs

- The static map remains a parallel source of truth while the flag is off
  (flag-off behavior is unchanged and still covered by
  `tests/test_permissions.py`).
- SSE chat endpoints now take a request-scoped `db` to resolve grants
  before streaming; the stream itself still owns its session.

## Alternatives considered

- **Drop the flag in the same change (always-DB).** Rejected for now:
  it changes behavior for every deployment. Pending maintainer sign-off;
  if approved, the removal lands as a second commit on the same branch.
- **Per-caller inline flag branches.** Rejected: six call sites would each
  duplicate the branch; the two helpers keep one chokepoint.

## How to verify the rule still holds

- `backend/tests/test_rbac_step4.py` — `role_id` persistence on
  create/update/custom paths, the FK-aware delete guard, and flag-on
  caller behavior with a custom role + override.
- `backend/tests/test_rbac_database_parity.py` — DB == static for system
  roles (unchanged).
- `backend/tests/test_rbac_database_switch.py` — gate and `/me` via the DB
  (unchanged).
- Grep: no `has_permission(` / `get_role_permissions(` runtime caller
  outside `permissions.py`, the flag-off legs, and tests.

## References

- `backend/app/core/auth/rbac.py` — `granted_permissions_for`,
  `has_permission_for`, `resolve_role_id`
- `backend/tests/test_rbac_step4.py`
- Issue #46 (DB RBAC), ADR 0024
