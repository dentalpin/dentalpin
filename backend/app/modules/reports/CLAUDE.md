# Reports module

Cross-module reporting: billing, budgets, scheduling.

## Public API

Routes mounted at `/api/v1/reports/`.

## Dependencies

`manifest.depends = ["patients", "agenda", "catalog", "budget", "billing", "payments"]`.
Read-only consumer of every business module.

## Permissions

`reports.billing.read`, `reports.budgets.read`,
`reports.scheduling.read`, `reports.financial.read`,
`reports.patient_stats.read`, `reports.operational.read` (v0.2.0;
the last two are reserved for the next families).

## Tools exposed

Agent tools in `tools.py` (wrap the report services, no logic duplicated).

| Tool | Category | Wraps | Permission |
|---|---|---|---|
| `billing_report` | READ | `BillingReportService.get_summary` | `reports.billing.read` |
| `top_clients_by_billing` | READ | `BillingReportService.top_clients_by_billing` | `reports.billing.read` |
| `scheduling_report` | READ | `SchedulingReportService.get_summary` | `reports.scheduling.read` |
| `financial_report` | READ | `FinancialReportService` aging + trend | `reports.financial.read` |

**Off-books boundary.** The billing tools expose the **invoice axis only**
(gross invoiced amounts). They strip paid / pending / overdue, because
those equal the invoiced-minus-collected diff clinics keep off-record.
The collection axis lives in `payments/tools.py`; the copilot system
prompt forbids surfacing the difference.

## Events emitted

None.

## Events consumed

None today — reports are computed on demand from underlying tables.

## Frontend slots exposed

| Slot | Ctx | Consumer |
|---|---|---|
| `reports.categories` | `{}` | **Deprecated** — kept for backwards compatibility only. The new `/reports` dashboard renders drill-down chips natively (including a hardcoded "Cobros" chip since `payments` is in `manifest.depends`). The slot is no longer rendered by the dashboard page, so any registered consumer becomes dormant. Future modules should use `reports.dashboard.widgets` instead. |
| `reports.dashboard.widgets` | `{ filters: Ref<{ from: string, to: string }> }` | Optional. Any module can inject a widget into the manager dashboard. The `filters` ref is the same one the native cards observe, so injected widgets share the date range without coordinating with the page. |

Reports never imports its slot consumers — the registry is the only
contract.

## Lifecycle

- `removable=False` — but a candidate for `removable=True` since this
  is a pure read-side module.

## Gotchas

- **Reads-only.** No writes from this module to other modules' tables.
- **Aggregations should be paginated and indexed.** Don't issue
  unbounded scans across multi-million-row tables.
- **Permissions are per-report-family.** Adding a new report =
  adding a new permission, registry-prefixed.

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md`
- `docs/adr/0005-relative-permissions.md`

## CHANGELOG

See `./CHANGELOG.md`.
