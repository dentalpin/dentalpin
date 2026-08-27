# Changelog — catalog module

## Unreleased

- fix(#101): a failed catalog load shows an error banner with Retry instead of the 'no items' empty state (which even offered the seed CTA on a mere fetch failure).

- fix(#127): every icon-only button in the module's frontend has an i18n-sourced `aria-label` (screen readers announced them as just "button").

- feat(#204): `VatType.legal_note` (`cat_0004`) — statutory clause invoices print when a line uses the VAT type. The "es" preset seeds the art. 20.Uno.5º LIVA exemption text on the exempt type (migration backfills existing ES clinics); the generic preset stays clean. Exposed on the VAT type schemas; editable on system types alongside `is_default` (#237 precedent).

- fix(#237): `PUT /catalog/items/{id}` no longer rejects every edit on
  system items. Price, cost, VAT, names, duration, sessions and `is_active`
  are editable; only structural fields (`SYSTEM_ITEM_LOCKED_FIELDS`) return
  403 when changed. Modal: `is_active` switch enabled, tooltip on the
  *System* badge, 403 toast shows the server detail.
- fix: the treatment modal sent `odontogram_mapping.visualization_rules`
  as the legacy string list, so saving any mapped treatment (create or
  edit) failed with 422. It now sends only type + clinical category; the
  layered rules stay server-owned.
- fix: `GET /catalog/odontogram-treatments` also returns **unmapped
  global-scope items** (`global_mouth`/`global_arch`) with
  `odontogram_treatment_type`/`clinical_category` as `null` — hygiene and
  diagnostic treatments (limpieza, primera visita, radiografía…) were
  invisible to the TreatmentBar because none of them carries a
  `TreatmentOdontogramMapping`. Unmapped tooth/multi_tooth items stay
  excluded; `/by-category` skips the null category (contract unchanged).
  `OdontogramTreatmentResponse` mapping fields are now nullable/defaulted.

- fix(#184): type-check clean — VAT-type toasts use semantic colours; `useCatalog` passes typed payloads to `useApi` without `Record` casts; `CatalogItemModal` builds a typed payload (create narrows the required fields instead of casting), option lists are typed to the form's unions, `UTextarea :rows` is a number; VAT badge colours are `UiColor`.
- feat(onboarding): the `catalog-empty` getting-started step resolves inline — `CatalogSeedQuickModal` calls `POST /catalog/seed` from the dashboard card, or hands off to `/settings/catalog`.

- feat: `POST /catalog/seed` (`catalog.admin`) loads the stock VAT types, categories and treatments for the clinic — idempotent repair path for installs created before `clinic.created` seeding existed (≤ v2.2.2) or where that seed failed silently. Surfaced as "Load default catalog" in the empty state of `/settings/catalog`.
- feat: category management UI (`CatalogCategoriesModal`) — create, rename, reorder, deactivate/reactivate from `/settings/catalog`. The category CRUD endpoints and composable existed with no consumer; the treatment modal requires a category, so a clinic with none could not create treatments.
- fix: `PUT /catalog/categories/{id}` now finds inactive categories, so a soft-deleted category can be reactivated (`is_active: true`); previously 404.
- fix: `seed_catalog` summary reports `vat_types` *created* (was the preset size), consistent with `categories`/`items`.
- refactor: `seed_clinic_defaults(db, clinic_id)` derives `vat_preset`/`with_prices` from the clinic row; `on_clinic_created` and the seed endpoint share it.
- docs(#183): `on_clinic_created` documented as own-session — `clinic.created` is published after setup commits, and seeding must not stretch the signup transaction.
- feat(onboarding): getting-started rule `catalog-empty` (frontend plugin) — flags a clinic with no catalog items on the dashboard card.

- feat(onboarding): subscribe to `clinic.created` — seed VAT types by country preset (`VAT_PRESETS`: `es` | `generic`), categories and the default catalog for every new clinic; `seed_catalog(..., vat_preset, with_prices)` (non-EUR → prices 0).

- i18n: add `ta` fallback to the agent-tool catalog name resolver so
  Tamil-localized treatment names resolve.

- fix(i18n): the REST-AMAL seed item had its Tamil name under a stray
  `"name"` key instead of `"ta"` (#165 follow-up).

- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- fix(ui): surface the API error instead of a generic toast in the VAT-type composable (load, create, update, delete).
  `catch {}` discarded the server's message, so any failure read as
  "Error" with no way to tell what went wrong. Now via
  `errorMessage()` / `errorDetail()`.

- i18n: add `pt` fallback to the agent-tool catalog name resolver so
  Portuguese-localized treatment names resolve.

- fix(frontend): error toasts in `useCatalog` now show the exact API
  error `detail` (string or 422 validation list) instead of always
  falling back to the generic "Error al crear/actualizar/eliminar"
  message. Generic text remains the fallback for network errors.

- i18n: correct French dental terminology in seed data (Contention,
  Bracket, Scellement de sillons, Fluoration, Diagnostic, ...).

- i18n: add French names/descriptions to seed data (categories,
  treatment items, session labels, VAT type names).

- feat(tools): expose `list_catalog_items` + `get_catalog_item` READ
  agent tools (wrap `CatalogService`) so the copilot can read the
  treatment catalog — name, code, category, price, duration, scope.

- feat(seed): cover advanced surgical, periodontal and orthodontic
  techniques that any modern Spanish clinic offers and the Gesdén
  importer was previously dumping into ``Importado de Gesdén``. New
  catalog items: ``SURG-PRP`` (Plasma rico en plaquetas / PRGF),
  ``SURG-PERIIMP`` (tratamiento de periimplantitis), ``SURG-BONE-VERT``
  + ``SURG-BONE-HORIZ`` (aumento óseo vertical y horizontal),
  ``SURG-SINUS-CLOSED`` (elevación de seno cerrada / atraumática),
  ``PERIO-GINGIV`` (gingivectomía), ``PERIO-SURG-RESECT`` +
  ``PERIO-SURG-REGEN`` (cirugía periodontal resectiva y regenerativa),
  ``ORTO-TAD`` (microtornillo / anclaje esquelético temporal),
  ``ENDO-APICOFORM`` (apicoformación), ``PED-SPACE-COMPOUND``
  (mantenedor de espacio compuesto). Renames ``PED-FILL-TEMP`` from
  "Obturación en pieza temporal" to "Obturación en dentición
  temporal" — the standard Spanish wording, disambiguates from
  ``REST-TEMP`` (temporary filling material on any tooth).
- feat(seed): broaden coverage for Gesdén imports — add 36 treatments
  across diagnóstico (urgencia, segunda opinión, telerradiografía),
  preventivo (tartrectomía con curetaje, profilaxis infantil),
  restauradora (reconstrucción amplia, recementado de corona, corona
  sobre endodonciado, pilares de cicatrización/definitivo, reparación
  de obturación), endodoncia (apertura cameral urgente, recambio
  medicación, endo en temporal), periodoncia (curetaje por sextante,
  estudio periodontal, férula post-RAR), cirugía (injerto conectivo,
  alargamiento coronario, exéresis de quiste, exodoncia de incluido,
  regularización ósea), ortodoncia (cementado / descementado de
  bracket, separadores, expansor palatino), estética (reconstrucción
  estética, eliminación de pigmentación), prótesis (provisional
  removible, ajuste oclusal), odontopediatría (extracción / obturación
  en temporal, pulpectomía). Lifts the seed from 82 to 118 items so
  the migration_import fuzzy matcher finds a real destination instead
  of dumping treatments in ``Importado de Gesdén``.
- feat(seed): add catalog items for implant-supported crowns —
  ``REST-CROWN-IMPL-MC`` (metal-ceramic), ``REST-CROWN-IMPL-ZIR``
  (zirconia) and ``REST-CROWN-IMPL-PROV`` (provisional). They map to
  the new odontogram clinical types ``crown_on_implant`` and
  ``provisional_crown_on_implant``.
- feat(sessions): new ``CatalogItemSession`` entity defines named,
  priced steps for treatments billed in stages (e.g. crown: "Toma de
  medidas" 200€ + "Colocación" 600€). Sum of session prices must
  equal the item ``default_price`` (422 on mismatch). Updates replace
  the template atomically. Migration ``cat_0003`` adds the table.
  Frontend admin ``CatalogItemModal`` gets a "Sesiones" section with
  editor + sum-validation chip.
- perf(list): ``CatalogService.list_items`` now counts directly via
  ``COUNT(TreatmentCatalogItem.id)`` instead of materialising the
  joined data query as a subquery.
- fix(isolation): drop the cross-module imports of
  ``billing.InvoiceItem`` and ``budget.BudgetItem`` from
  ``CatalogService.get_popular_items``. Catalog is foundational
  (``manifest.depends = []``) — importing consumer-module models
  inverted the DAG and blocked uninstall of billing / budget. The
  usage ranking now reads the sibling tables through a single raw
  ``UNION ALL`` SQL fragment and falls back to the most recent
  active items when a clinic has no budgets / invoices yet.
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Treatment catalog with categories.
- VAT types with versioning.
- Pricing rules in `pricing.py`.
- Idempotent seed in `seed.py`.
