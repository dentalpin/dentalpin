# Changelog — patient_relationships module

## Unreleased

- feat(#131): German (de) locale for the module's frontend layer.

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.
- Renamed the module `patient_admin` → `patient_relationships` (the old
  name was too generic for what it does). Nothing had shipped, so this
  is a clean rename, no compat aliases: module/branch/entry-point name,
  table `patient_admin_relationship` → `patient_relationships` (+ index
  and constraint names), revisions `padm_*` → `prel_*`, API prefix
  `/api/v1/patient_relationships`, and permissions collapsed to
  `patient_relationships.read`/`.write` (bare `read`/`write` from
  `get_permissions()`, the patients/recalls convention — the old
  `patient_admin.relationships.*` double-noun went away with the
  rename). Existing dev installs of the old name must be uninstalled
  (or manually dropped) before upgrading — there is no migration path.
- `auto_install` flipped to `False`: optional modules ship inactive and
  the admin activates them from the module admin UI (repo policy).
- Added `clinic_id` to the two remaining unscoped queries: the
  duplicate-pair check in `create_relationship` and the related-patient
  name lookup in `list_relationships_for_patient`. Both were safe in
  practice (inputs already validated against the clinic upstream) but
  violated the "every query filters by clinic_id" rule.
- `relationship_type` is now a `Literal` on the create schema (422 on
  bad input, like the rest of the repo) instead of a manual 400 check
  in the service.
- Added the round-trip uninstall test required for `removable=True`
  modules (`test_uninstall_roundtrip.py`, `alembic_roundtrip` marker).
- Frontend: slot order 60 → 55 (60 tied with patients' QuickActionsCard,
  which is meant to render last); `catch (e: any)` → `unknown` +
  structural narrowing (repo lint rule); `ApiResponse` imported from
  `~~/app/types` instead of a local re-declaration; added `pt` and `ta`
  locales (all five UI locales, per the i18n checklist).
- Docs: endpoint paths in `docs/technical/patient_relationships/permissions.md`
  now include the real `/api/v1/patient_relationships` prefix the plugin loader
  mounts the router under.
- `get_relationship` now filters by `clinic_id` in addition to
  `relationship_id`, matching every other lookup in this module. Not
  previously exploitable (the router's own `patient_id` match check
  blocked it), but a future caller that reached `get_relationship`
  directly would have inherited an unscoped lookup — closed as
  defense in depth.
- `prel_0001`'s migration now declares `depends_on = ("pat_0003",)`
  for its FK to `patients.id`, and its docstring's claim of "no
  dependency on another module's branch" is corrected — `patients`
  lives on the unlabeled/core chain, not inside `patient_relationships`'s own
  branch, so this dependency needed to be explicit.
- Added `CLAUDE.md` and this file.
- Added a tenant-isolation test for `get_relationship`.

## 0.2.0 (prior)

- `prel_0002`: dropped the insurance exemption status table —
  exemption is now a computed flag off systemic-disease reference
  data, not manually entered here.
- Initial schema (`prel_0001`): patient-to-patient relationships with
  a derived inverse label at read time.
