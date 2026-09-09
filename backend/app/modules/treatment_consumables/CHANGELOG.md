# Changelog — treatment_consumables module

## Unreleased

- feat(i18n): Arabic (ar) locale for the module's frontend layer.
- feat(i18n): the frontend layer's directional spacing, borders, text alignment and inset positioning now resolve against the document direction (physical→logical CSS utilities, Arabic RTL support).

- feat(#226): handle `odontogram.treatment.performed` (subscription
  inversion) — resolve this module's links for the performed catalog
  item and deduct stock via `InventoryService.apply_consumption`
  (transactional per ADR 0019; idempotent per treatment; clamps at
  zero). The module emits nothing and still writes only its own table.

- fix(#101): the module's frontend adopts the useApi error contract — 400/409/422 failures the UI used to swallow now toast the backend's message; calls whose surrounding code already presents the error pass `errorToast: false` (single toast), and hand-built error reads use the shared `errorMessage`/`errorDetail` helpers.

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

## 0.1.0 — initial release

- Junction table linking catalog treatments to inventory items with a
  quantity per link. Pure mapping — no stock deduction (lands with the
  inventory core upgrade #226).
- DB-level FKs into `catalog` and `inventory` (CI-enforced against the
  `depends` declaration); unique (clinic, treatment, item) triple.
- Create validates both endpoints inside the caller's clinic (404 on
  foreign rows) and answers 409 on duplicate pairs — from the unique
  constraint, so concurrent creates get the same 409 instead of a 500.
- Optional per-link note ("per session", "only if surgery"), editable
  and clearable from the API and the UI.
- `/treatment-consumables` page: history table with resolved names from
  both modules, quantity rendered with the item's unit, per-side search
  boxes fed by one permission-gated `link-options` endpoint, quantity +
  note editing, unlink confirmation, and toasts on failure (duplicate
  pairs get their own message).
- Agent tool `get_treatment_consumables` (READ, cloud-eligible).
- `auto_install=False`, `removable=True`, own Alembic branch
  (`treatment_consumables`), uninstall round-trip + tenant isolation +
  duplicate-pair tests.
- Default roles: admin full, dentist read-only.
- UI strings in en/es/fr/pt/ta/de/hu; `nav.treatmentConsumables` added
  to the host locales so the sidebar entry is translated.
- Docs: technical overview/events/permissions pages, user manual en+es
  with real `last_verified_commit`, module CHANGELOG, CLAUDE.md tools
  section.
