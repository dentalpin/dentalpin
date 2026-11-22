# Changelog — inventory_reorder

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- fix(#992): a repeated `item_ids` entry counts once. Each supplier's PO is committed by `create_order`, so a duplicate used to leave the earlier suppliers' drafts behind and answer 400.
- fix(#677): the `generate_reorder_orders` tool parameter `item_ids` is
  typed `list[UUID]` instead of `list[str]`.
  The tool schema now advertises `format: uuid`, and a malformed id is
  rejected by `tool_registry.call`'s validation step naming the parameter,
  rather than reaching the handler and raising `badly formed hexadecimal
  UUID string`, which named nothing.

### Added

- Rebuilt fresh off current `main` (roadmap #227-4): sourcing excludes
  soft-deleted vendor links and inactive contacts; agent order generation
  passes `created_by=None` (AgentContext carries no acting user).
- Reorder suggestion engine (`ReorderService.compute_suggestions`):
  `usage_90d` from negative stock movement deltas, preferred-supplier
  sourcing, `reorder_point = max(min_quantity, ceil(daily_usage ×
  lead_time))` and, when `stock + on_order` is below it,
  `suggested_quantity = reorder_point + ceil(daily_usage × 30) −
  (stock + on_order)` (order up to the point plus 30 days of cover),
  for active items with demand and a supplier link.
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