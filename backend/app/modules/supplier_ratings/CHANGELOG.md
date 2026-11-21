# Changelog — supplier_ratings

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- fix(#976): `PATCH /reviews/{id}` with `null` for `score` is a 422 (was a 500 from the NOT NULL column).
- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- fix(#677): the `get_supplier_rating` / `create_supplier_review` tool
  parameter `supplier_id` is typed `UUID` instead of `str`.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

### Added

- `PATCH /reviews/{id}` is a partial update: omitted fields are left untouched.

- Rebuilt fresh off current `main` (roadmap #227-5): unknown-supplier
  ids answer 404 (was 400); duplicate ratings answer 409 from the unique
  constraint under race; agent review creation passes `created_by=None`
  (AgentContext carries no acting user).
- `supplier_reviews` table (own Alembic branch `rat_0001`, `depends_on`
  `contacts@con_0001`) — one manual 1–5 communication rating per
  (clinic, supplier) with score CHECK, comment, `created_by`, timestamps;
  registered in `backend/alembic.ini`.
- On-demand delivery/quality metrics from purchase order history:
  `po_count`, `received_count`, `received_with_due_date`,
  `on_time_deliveries`/`on_time_rate`, `received_quantity`,
  `rejected_quantity`/`reject_rate` — computed live, never persisted.
- Endpoints under `/api/v1/supplier_ratings/`: paginated list (GET),
  single-supplier detail (GET), create review (POST, 201, 409 on
  duplicate), update review (PATCH) and delete review (DELETE, 204).
- Copilot tools `list_supplier_ratings` (READ), `get_supplier_rating`
  (READ) and `create_supplier_review` (WRITE), all
  `exposes_free_text=True`.
- Module docs (`docs/technical/supplier_ratings/{overview,permissions,events}.md`),
  module `CLAUDE.md` and this CHANGELOG.