# Changelog — patient_segments

## Unreleased

- fix(#1134): `PATCH /segments/{id}` with `name: null` is a 422, not the duplicate-name 409.

- feat(i18n): Hindi (`hi`) locale for the module's frontend layer.
- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- Initial module: clinic-local patient tags for grouping and campaigns
  (segments CRUD, assign/unassign, member listing). No points, no
  expiry — grouping only.
- Groups card uses the shared `SummaryCard` shell; names are trimmed and
  blank names rejected; `color` must be `#rrggbb`.
