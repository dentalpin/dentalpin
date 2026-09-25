# Changelog - orthodontics

## Unreleased

- feat: explicit status machine (`VALID_TRANSITIONS`, issue #505 review):
  `transferred_out` terminal, `finished` reopens only to `active`;
  `finished_at` set once and never cleared, `reopened_at` stamps the
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
