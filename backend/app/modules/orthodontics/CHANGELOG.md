# Changelog - orthodontics

## Unreleased

- fix: current `useApi`/`USelect` contracts (`{ query }`, typed
  update handler) + import depth + `noUncheckedIndexedAccess`
  first-case guard in the layer.
- Slice-a (issue #270): cases with appliance/status lifecycle, per-visit
  controls with chip procedures + hygiene + next-control interval,
  "in mouth now" wire state, photo evolution via `ortho_case` /
  `ortho_control` media owners, chip-catalog settings seeds, inbox page,
  patient sub-tab + summary card. No money code yet — installments,
  recall upsert, plan/appointment links, and copilot tools are slice-b.
