# Changelog — patient_segments

## Unreleased

- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
- Initial module: clinic-local patient tags for grouping and campaigns
  (segments CRUD, assign/unassign, member listing). No points, no
  expiry — grouping only.
- Groups card uses the shared `SummaryCard` shell; names are trimmed and
  blank names rejected; `color` must be `#rrggbb`.
