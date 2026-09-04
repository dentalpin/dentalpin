# Changelog — inventory_reorder

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Rebuilt fresh off current `main` (roadmap #227-4): sourcing excludes
  soft-deleted vendor links and inactive contacts; agent order generation
  passes `created_by=None` (AgentContext carries no acting user).
- Reorder suggestion engine (`ReorderService.compute_suggestions`):
  `usage_90d` from negative stock movement deltas, preferred-supplier
  sourcing, `reorder_point = ceil(daily_usage × lead_time)` and
  `suggested_quantity = ceil(reorder_point − (stock + on_order))`,
  returning only positive suggestions for active items with demand,
  a supplier link and a set lead time.
- `GET /api/v1/inventory_reorder/suggestions` (read) and
  `POST /api/v1/inventory_reorder/orders` (write, 201) — the latter
  groups the requested suggestions into one draft purchase order per
  supplier via `PurchaseOrderService.create_order`, 400 on items
  without a current suggestion.
- Copilot tools `list_reorder_suggestions` (READ) and
  `generate_reorder_orders` (WRITE), both `exposes_free_text=True`.
- No-op Alembic revision `ir_0001` (isolated `inventory_reorder`
  branch) so `removable=True` uninstalls cleanly; registered in
  `backend/alembic.ini`.
- Module docs (`docs/technical/inventory_reorder/{overview,permissions,events}.md`)
  and this CHANGELOG.