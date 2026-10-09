# Changelog - orthodontics

## Unreleased

- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- fix (maintainer review, round 3): plan picker uses the correct
  `/api/v1/treatment_plan/...` prefix; item labels resolve from the
  plan detail (`names[locale] ?? names.es ?? first value`,
  `clinical_type` and `Item N` fallbacks); schedule modal has labeled
  inputs with the pending total shown and client-side total check
  (single toast via `errorToast: false`); session badges show
  `label · amount`; plan statuses translated, pickers full-width.
- fix (maintainer review, round 2): schedule generation replaces pending
  sessions and validates the total (`ort_0003` unique plan link answers 409
  on double-link); money is `Decimal` end to end; session labels come from
  the frontend; session pointers are validated; plan link/unlink/schedule/
  settings surface errors with toasts and unlink confirms; Collect shows
  only with payments installed + read; pickers show treatment names,
  translated statuses and upcoming appointments with time; dead validators
  removed; tool copy fixed and overdue total precedes the limit;
  `treatment_plan_id` unique (`ort_0003`).
- fix(#590): the clinic-membership checks behind control registration
  tolerate duplicated membership rows (`.limit(1)` existence read).
  `clinic_memberships` has no unique `(clinic_id, user_id)` constraint,
  so a duplicate used to 500 with `MultipleResultsFound`.
- feat(i18n): Telugu (`te`) locale for the module's frontend layer.
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
- Follow-ups (issue #270): copilot tools `get_ortho_case_status` /
  `list_overdue_ortho_controls` / `register_ortho_control`, chip-catalog
  settings editor (`PUT /settings` + inbox section, `settings.manage`).
- Slice-b (issue #270): optional treatment-plan link (`treatment_plan_id`
  + `plan_item_id`, nullable for transfer patients), installment schedule
  generation through the plan session API, read-only installments widget
  data (counts only, ADR 0010), deep-link-only "Collect installment" to
  `/payments?patient_id=` (payments honors it on mount), recall upsert
  (`ortho_review`, paused freezes generation), appointment link +
  session audit pointer on controls, `transferred_out` plan-close
  suggestion flag.
- Slice-a (issue #270): cases with appliance/status lifecycle, per-visit
  controls with chip procedures + hygiene + next-control interval,
  "in mouth now" wire state, photo evolution via `ortho_case` /
  `ortho_control` media owners, chip-catalog settings seeds, inbox page,
  patient sub-tab + summary card.