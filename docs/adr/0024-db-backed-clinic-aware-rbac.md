# 0024 — DB-backed, clinic-aware RBAC (persist roles & grants)

- **Status:** accepted
- **Date:** 2026-09-03
- **Deciders:** DentalPin core maintainer (@martinezsalmeron), lamanji
- **Tags:** rbac, security, multi-tenancy

## Context

Roles and their permissions are hardcoded in
`backend/app/core/auth/permissions.py` (`ROLE_PERMISSIONS`) plus each
module's `manifest.role_permissions`, merged at runtime by
`get_role_permissions()`. That works, but an operator cannot define a
**custom role** for their clinic, nor tweak a system role's grants per
clinic, without a code change and a deploy.

Custom roles also raise a tenancy subtlety: a role is only meaningful in
the clinic that defined it. The permission model must therefore be
**clinic-aware** — the same role name can resolve to different effective
grants in different clinics (per-clinic overrides), and custom roles are
scoped to the clinic that created them.

Issue #46 is the DB migration + custom-role feature; #47 is the admin UI
that consumes it.

## Decision

Persist RBAC in the database and resolve it clinic-aware at the firewall
(`require_permission`) and in `/me`, mirroring the legacy static grant set
exactly so there is **no parallel source of truth**.

- New tables: `roles`, `permissions`, `role_permissions`,
  `module_default_role_permissions`, `clinic_role_overrides`.
- The five system roles (`admin`, `dentist`, `hygienist`, `assistant`,
  `receptionist`) are rows with `clinic_id IS NULL`; a clinic-created
  **custom role** is a row with `clinic_id` set.
- `seed_rbac` (every boot, flag or not; module install/uninstall restarts
  the backend) reconciles system
  roles' `role_permissions` to be identical to the legacy
  `get_role_permissions()` merge — the parity test
  (`tests/test_rbac_database_parity.py`) is the gate.
- Wildcards (`*`, `module.*`) are stored literally and expanded at lookup
  / `/me` via the existing `permission_matches` / `expand_permissions`.
- `clinic_role_overrides` records a clinic's add/remove on a system role;
  custom roles express their full intent in `role_permissions` directly.
- `require_permission` keeps its signature (zero route churn); internally
  it resolves via `ctx.clinic_id`. A `RBAC_FROM_DB` flag (issue #46 release,
  default off) switches the firewall/`/me` to the DB path; once parity and
  review clear it, the flag flips on and the static map is dropped. While
  it is off, custom roles can be prepared but not assigned to members (the
  static map would resolve them to nothing), and the `admin` system role
  never accepts revoke overrides (a clinic could lock itself out).
- `clinic_memberships.role` string stays this release as the read path /
  insert default; the new nullable `role_id` FK becomes the authority in a
  follow-up (dropping `role`).

## Consequences

### Good

- Admins create clinic-scoped custom roles and override system-role grants
  per clinic without a deploy — the backend the #47 admin UI consumes.
- Tenancy is explicit: custom roles and overrides are keyed by `clinic_id`
  and never leak across clinics.
- The parity test keeps the DB a faithful drop-in, so switching
  `require_permission`/`/me` is gate-able and reversible.

### Bad / accepted trade-offs

- Every gated request under the DB path incurs a DB-backed permission
  resolution (mitigated by a per-process resolution cache; see
  `rbac.py` `_role_set_cache`).
- Custom role names ride the legacy `clinic_memberships.role` `String(20)`
  column this release, so they are capped at 20 chars until `role` is dropped.
- The sync callers that still use static grants (copilot nav/fallback,
  plugins router `_nav_visible`) keep the static map until a follow-up
  migrates them; they are non-authoritative display paths.
- Uninstalling a module leaves orphaned `permissions` rows (never granted
  to a role) — harmless, and reconciled at next boot.

## Alternatives considered

- **Per-clinic role cloning.** Rejected — duplicates every system role's
  grant set per clinic and makes system-role changes a migration, not an
  update.
- **Full DB for every sync caller immediately.** Rejected — the copilot /
  navigation call sites are synchronous; migrating them all in one change
  widens blast radius. The firewall + `/me` are the authority and ship
  first.

## How to verify the rule still holds

- `backend/tests/test_rbac_database_parity.py` — DB == legacy static for
  every system role (no parallel source of truth).
- `backend/tests/test_rbac_database_switch.py` — the gate and `/me`
  resolve via the DB under `RBAC_FROM_DB`.
- `backend/tests/test_roles_api.py` — custom-role CRUD, per-clinic
  overrides, resource-isolation.
- `alembic heads` keeps `0007_rbac_database` as the core head; the RBAC
  migration is on the core chain, not a module branch.

## References

- `backend/app/core/auth/permissions.py` — `ROLE_PERMISSIONS`,
  `CORE_PERMISSIONS`, `has_permission`
- `backend/app/core/auth/rbac.py` — DB-backed resolver
- `backend/app/core/auth/seed_rbac.py` — idempotent seeder
- `backend/app/core/auth/router_roles.py` — `/api/v1/roles` management API
- `backend/app/core/auth/models.py` — RBAC tables + `role_id` FK
- `backend/alembic/versions/0007_rbac_database.py`
- Issue #46 (DB RBAC), #47 (admin UI)
