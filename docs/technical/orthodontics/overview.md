# orthodontics - overview

Orthodontic case tracking: monthly controls, archwires, photo
evolution (issue #270). Slice-a is clinical tracking only: cases with
appliance/status lifecycle, per-visit controls with chip procedures +
hygiene + next-control interval, "in mouth now" wire state,
start-vs-current photo evolution via media attachments, chip-catalog
settings seeds, inbox page, patient sub-tab + summary card.

Slice-b adds the money loop without new billing primitives: optional
plan link (nullable for transfer patients), installment schedule
generation through the plan session API, read-only installments widget
(counts only, ADR 0010), deep-link-only "Collect installment" to
`/payments?patient_id=`, recall upsert (`ortho_review`, paused freezes
generation), appointment link + session audit pointer on controls,
`transferred_out` plan-close suggestion.

## Later (v2, separate issues)

<`active` ↔ `paused`; either may finish or transfer out. `finished`
reopens only to `active` (explicit reopen path); `transferred_out` is
terminal. `finished_at` is stamped on each entry into a terminal state
and never cleared; a reopen stamps `reopened_at` instead, so the
end-of-treatment record survives (the replaced value travels in the
event's `previous_finished_at`). Same-status posts are accepted as note updates.

- Open-ended monthly pricing, per-tray aligner tracking, WhatsApp summary.
