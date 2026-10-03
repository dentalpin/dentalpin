# Changelog - orthodontics

## Unreleased

- fix(#590): the clinic-membership checks behind control registration
  tolerate duplicated membership rows (`.limit(1)` existence read).
  `clinic_memberships` has no unique `(clinic_id, user_id)` constraint,
  so a duplicate used to 500 with `MultipleResultsFound`.
- fix(#522): the new-case `start_date` default read the UTC day instead of the
  local one. Now uses `toISODate`.
- fix (maintainer review): inbox shows the patient's name (batched, no
  N+1); "Month X" counts calendar months from `start_date`, not controls;
  new-case modal asks for start date and orthodontist; case selector uses
  `USelect :items`; procedure chips translated; load/save/upload errors
  toasted; "Register control" hidden on closed cases; status change gated
  on `cases.write`, photo upload on `attachments.write`; editing a control
  re-derives the in-mouth wires; dead validators/asserts removed.
- feat: explicit status machine (`VALID_TRANSITIONS`, issue #505 review):
  `transferred_out` terminal, `finished` reopens only to `active`;
  `finished_at` never cleared (re-stamped on re-finish), `reopened_at` stamps the
  explicit reopen path; status-changed event carries
  `previous_finished_at`.
- fix: the module ships a single migration: `reopened_at` is created inline
  in `ort_0001` and `ort_0002` is gone, while the module is still unshipped
  (free now, impossible after release). The uninstall round-trip therefore
  targets `orthodontics@-1`.
- fix: `ort_0001` declares `depends_on = ("pat_0003",)` for the
  `patients.id` FK (current precedent; convention tracked in #507).

- fix: current `useApi`/`USelect` contracts (`{ query }`, typed
  update handler) + import depth + `noUncheckedIndexedAccess`
  first-case guard in the layer.
- Slice-a (issue #270): cases with appliance/status lifecycle, per-visit
  controls with chip procedures + hygiene + next-control interval,
  "in mouth now" wire state, photo evolution via `ortho_case` /
  `ortho_control` media owners, chip-catalog settings seeds, inbox page,
  patient sub-tab + summary card. No money code yet — installments,
  recall upsert, plan/appointment links, and copilot tools are slice-b.
