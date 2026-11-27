# Catalog module

Treatment catalog, categories, VAT types. Foundational pricing source
of truth for budgets and billing.

## Public API

Routes mounted at `/api/v1/catalog/`.

## Dependencies

`manifest.depends = []`. Foundational.

## Permissions

`catalog.read`, `catalog.write`, `catalog.admin`.

## Tools exposed

Agent tools in `tools.py` (wrap `CatalogService`, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `list_catalog_items` | READ | `CatalogService.list_items` | `catalog.read` |
| `get_catalog_item` | READ | `CatalogService.get_item` | `catalog.read` |

Both filter by `ctx.clinic_id`. `names`/`descriptions` are localized
JSONB; the tools collapse to `es` → `en` → first value for the agent.

## Events emitted

None.

## Events consumed

- `clinic.created` → `events.on_clinic_created` (own-session) seeds VAT
  types / categories / treatments via `seed.seed_clinic_defaults`. Failures
  are logged, not raised; the `catalog-empty` getting-started rule surfaces
  an empty catalog and `POST /catalog/seed` repairs it (same function).

## Lifecycle

- `removable=False`. Budget, billing, odontogram, treatment_plan all
  depend on this.

## Gotchas

- **Session template** (``CatalogItemSession``) is optional per item;
  when present, the sum of ``default_price`` across sessions must
  equal the item's ``default_price`` (tolerance ±0.01). PUT
  ``/items/{id}`` with ``sessions`` (list, even empty) replaces the
  template atomically via ORM ``item.sessions.clear()`` + re-append;
  omitting the key preserves the existing template. Consumers
  (treatment_plan) snapshot this template at plan-add time.
- **VAT types are versioned** — when changing a VAT rate, create a new
  version rather than mutating in place. Historical invoices must
  reproduce their original VAT.
- **`VatType.legal_note`** — statutory clause the invoice PDF prints
  when a line uses the type (e.g. the Spanish dental exemption,
  art. 20.Uno.5º LIVA — seeded by the `es` preset, backfilled by
  `cat_0004`). Clinic-owned even on system types (editable alongside
  `is_default`, #237 precedent). Billing reads it via
  `vat_legal_notes_for_invoice` (#204).
- **Pricing rules live in `pricing.py`** — keep service code thin and
  delegate calculations there.
- **Seed data** is shipped via `seed.py` and idempotent — re-running it
  must not duplicate categories. `seed_clinic_defaults` is the single entry
  point (derives preset/prices from the clinic); `seed_catalog` is the
  low-level worker.
- **System items are partially locked** — `SYSTEM_ITEM_LOCKED_FIELDS` in
  `router.py` (code, category, pricing strategy, scope, diagnostic,
  surfaces) return 403 only when the value actually changes; price, cost,
  VAT, names, duration, sessions and `is_active` are clinic-owned and
  editable. Rows are per-clinic and downstream consumers snapshot the
  price, so editing it never rewrites history (#237).
- **`update_item` treats `None` as "not sent"** except for the nullable
  `default_price`, `cost_price` and `default_duration_minutes`
  (`_CLEARABLE_ITEM_FIELDS`), where an explicit `null` (or a cleared
  input's `""`, read as `None` by the schema) clears the value (#740).
- **`surface_prices` is plain JSONB** — tier prices are stored as
  strings (`{"1": "60.00", ...}`, the seeder's format); the `SurfacePrice`
  schema type dumps the request's Decimals that way, since `json.dumps`
  cannot encode a Decimal (#1240). `pricing.py` reads them with
  `Decimal(str(v))`, so numbers stay readable too.
- **Categories are mandatory on items** (`category_id` NOT NULL). Anything
  that can leave a clinic with zero categories blocks treatment creation —
  keep the seed endpoint and the categories UI working.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`

## CHANGELOG

See `./CHANGELOG.md`.
