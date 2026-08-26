# Architecture Decision Records

Why we record decisions here:

- The repo grows; the *why* behind a constraint stops being obvious.
- AI agents and new contributors need durable, searchable context for
  rules they will otherwise question or accidentally undo.
- `git log` carries the *what*. ADRs carry the *why* + the *trade-offs
  considered* + the *consequences* if you break the rule.

## Convention

- Filename: `NNNN-kebab-title.md` — zero-padded sequence, never reused.
- First line: `# NNNN — Title`, with the number matching the filename.
- One decision per file. Short. ≤1 page when possible.
- Every ADR uses the same structure: see `TEMPLATE.md`.
- Status: `proposed` → `accepted` → optionally `superseded by NNNN` /
  `deprecated`. Never delete an ADR; supersede it.
- Date: the date status changed (ISO `YYYY-MM-DD`).
- Cite source files (`path:line`) and tests so the rule is verifiable.

## ADR vs `features/` / `technical/`

- `docs/adr/` — historical decisions that shape today's code. Read to
  understand why a rule exists.
- `docs/features/` — forward-looking product / UX briefs. *What* and
  *why* of a feature being shaped.
- `docs/technical/` — implementation plans and cross-cutting tech
  reference. *How* a feature is being built.

A design brief or tech plan may graduate to an ADR once the decision
is locked in and worth defending against future drift.

## When to write a new ADR

Triggers (any one):

- A rule has been broken once and we want to make sure it isn't again.
- A reviewer asked "why is it this way?" and the answer isn't in code.
- We chose between two reasonable approaches and the loser will keep
  resurfacing.
- A constraint is imposed by an external system (regulator, vendor,
  licensor) and we need to capture it once.

## Index

There is deliberately no index table here. The one this section used
to hold rotted silently — it stopped at 0006 while the directory held
21 files (issue #300) — and an index that reads as complete while
covering a fraction of the decisions invites re-litigating what was
already locked in.

**The directory listing is the index.** Filenames carry number and
title (`ls docs/adr/` reads as a table of contents), the first line of
each file repeats them, and `status`/date live inside the file. CI's
`docs-layout` job enforces the invariants that keep the listing
trustworthy: strict `NNNN-kebab-title.md` names, no duplicate and no
skipped numbers, and a first-line heading that matches the filename
(issue #299, `scripts/check_docs_layout.py::check_adrs`).
