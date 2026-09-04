# Changelog — supplier_ratings

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

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