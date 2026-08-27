# Changelog — reports module

## Unreleased

- fix(#101): report dashboards render an error banner with Retry on fetch failure instead of 0 € / empty charts (shared fetch-failed flag across the 24 fetchers + dashboard snapshot).

- fix(#242): patient billing KPI "Trabajo completado" is no longer permanently 0. The `completed` budget status was removed in 2026-04, so `get_patient_summary` now derives `work_completed` from **fully invoiced** accepted quotes (every line's `invoiced_quantity` ≥ `quantity`), and `work_in_progress` becomes the complement (accepted, not yet fully invoiced) so the two KPIs partition the accepted total.
- fix(#201): dashboard week-glance no longer shows `↘ NaN%` on a fresh clinic — `delta()` coerces its operands (the API sends monetary fields as decimal strings, so the `!prev` guard never fired for `"0.00"`) and treats a non-finite percentage as no-delta.

- feat(#181): `get_patient_summary` returns `total_discount` (Σ line + global discounts on the patient's budgets).
- fix(#184): type-check clean — sibling composable imports are relative (the `~/` form resolved to the host for vue-tsc and made half the page implicitly `any`), ISO dates via `.slice(0, 10)`, budget status badge colour is `UiColor`.
- style(lint): first ESLint pass over this module's frontend layer —
  module layers were outside the linter's base path until now, so
  CI had never checked them. Mostly auto-fixed formatting; see the
  PR for the handful of manual fixes.

- feat(agents): expose `tools.py` — `billing_report`,
  `top_clients_by_billing`, `scheduling_report` (all READ). Off-books:
  the billing tools are **invoice-axis only** (gross invoiced; never
  paid/pending/overdue). Adds `BillingReportService.top_clients_by_billing`.
  Issue #81 P0 batch.

- ux(dashboard): drill-down chips moved from the page footer up to a horizontal nav row right under the header, so detail pages stay one tap away. The legacy `reports.categories` slot is no longer rendered (size mismatch with the new compact chips); the "Cobros" chip is hardcoded since `payments` is already in `manifest.depends`. The slot stays registered for backwards compat but is dormant — future contributions should target `reports.dashboard.widgets`.
- feat(dashboard): rewrite `/reports` index from a 3-card nav into an integrated manager dashboard. Hero KPIs (caja cobrada, saldo a favor, producción, top forma de pago), charts (cobros en el periodo, producción por doctor), operational tiles (pacientes nuevos, no-show, ticket medio cobrado) and aging-receivables. Mobile-first responsive grid, sticky date-range filter with URL persistence, per-card loading skeletons, point-in-time snapshot badge on filter-immune tiles, and a new `reports.dashboard.widgets` slot for third-party widget injection. Detail pages preserved as drilldown. Zero new backend endpoints: consumes existing `/payments/reports/*` and `/reports/scheduling/*` over HTTP, no cross-module service imports.
- fix(i18n): ``useReports.getPaymentMethodLabel`` was calling the non-existent ``invoice.paymentMethods.*`` i18n key and rendering the raw key as fallback; now uses the shared ``paymentMethodLabel`` util reading the canonical ``invoice.payments.methods.*`` path.
- safety(billing-overdue): ``GET /reports/billing/overdue`` accepts a
  ``limit`` query parameter (default 200, max 1000) and the service
  enforces it. Previously the endpoint returned every overdue
  invoice for a clinic, which scaled with years of unpaid balance.
- docs(user-manual): reescribir pantallas con guía operativa (ES + EN).
- Added per-module `CLAUDE.md` for AI-agent context (2026-04-27).

## 0.1.0 — initial

- Billing, budget, and scheduling report families.
- Read-only across the business modules.
