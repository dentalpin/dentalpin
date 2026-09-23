# orthodontics - overview

Orthodontic case tracking: monthly controls, archwires, photo
evolution (issue #270). Slice-a is clinical tracking only: cases with
appliance/status lifecycle, per-visit controls with chip procedures +
hygiene + next-control interval, "in mouth now" wire state,
start-vs-current photo evolution via media attachments, chip-catalog
settings seeds, inbox page, patient sub-tab + summary card.

No money code in slice-a. Installments, recall upsert, the
treatment-plan/appointment links, copilot tools, and the settings UI
are slice-b / follow-ups (see Later below and the module CLAUDE.md).

## Later (slice-b + follow-ups, user-approved 2026-09-08)

- **Slice-b:** optional plan link (`treatment_plan_id` + `plan_item_id`,
  nullable for transfer patients), recall upsert (`ortho_review`;
  paused freezes generation), appointment link, `session_id` audit
  pointer, installments widget + deep-link-only "Collect installment"
  (ADR 0010: collection stays in the payments screen), `transferred_out`
  plan-close prompt.
- **Follow-ups:** chip-catalog settings UI (seed-only now), copilot
  tools (`get_ortho_case_status`, `list_overdue_ortho_controls`,
  `register_ortho_control`), v2 items from the issue (open-ended
  monthly pricing, per-tray aligner tracking, WhatsApp summary).
