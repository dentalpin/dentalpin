# Changelog — reports module

## Unreleased

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
