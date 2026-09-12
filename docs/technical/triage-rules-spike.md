# Triage rule-engine spike — design record (Stream 4b, design-only)

> Mining result first: `rahul1947/Orthodontist-Expert-System` (MIT) contains
> **no code** — course report PDFs + screenshots only. There is no rule
> engine to port. What follows is an original mini-design; the MIT license
> imposes no obligation since nothing is copied.

## Idea

Forward-chaining screening rules over data we already own (appointment
history, recall flags, patient flags, treatment plans) producing
suggestions, never decisions:

- `no_show x2 in 90d` → suggest confirmation-call task + tighter reminder.
- `perio diagnosis + no visit in 6mo` → suggest recall.
- `ortho consult + pano present + age band` → suggest #270 screening Julien.

## Shape (if ever built)

- Pure functions `evaluate_rules(patient_view) -> [suggestion]` — no tables,
  no migrations, no permissions beyond the reader's own.
- Surfaced through the existing copilot/agent tool path (READ tool) and the
  appointment slot (`appointment.completed.followup` pattern), never as
  autonomous writes. Human confirms every suggestion (copilot approval flow).
- Clinical-safety caption everywhere ("aid, never diagnosis"), same posture
  as the imaging modules.

## Status

Design-only, feeds #270. No branch, no code, nothing to verify. Revisit
when the orthodontics module (#270) is scoped.
