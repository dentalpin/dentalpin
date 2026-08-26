# India GST module

CGST/SGST/IGST billing compliance for Indian clinics (GSTIN, place of
supply, SAC codes, FY-scoped document numbering, credit-note reversal,
e-invoice applicability tracking).

## Public API

- Routes mounted at `/api/v1/india_gst/`.
- Key endpoints:
  - `GET/PUT  /india_gst/settings`                  — clinic GST profile; `india_gst.settings.read`/`.configure`
  - `GET/PUT  /india_gst/catalog-defaults`           — SAC defaults per treatment; `india_gst.catalog.manage`
  - `POST     /india_gst/tax-preview`                — stateless Decimal-safe breakdown; `india_gst.settings.read`
  - `PUT      /india_gst/invoices/{id}`              — draft-only GST fields (place of supply, SAC); `billing.write`
  - `GET      /india_gst/invoices/{id}/einvoice`      — e-invoice status; `india_gst.settings.read`
  - `POST     /india_gst/invoices/{id}/einvoice/retry` — always 409 in v1 (no provider); `india_gst.settings.configure`
  - `GET      /india_gst/reports/{summary,transactions,export}` — reconciliation report; `india_gst.reports.read`

## Dependencies

`manifest.depends = ["billing", "catalog"]`. Reads `TreatmentCatalogItem`
(catalog) for SAC-default resolution and `Invoice`/`InvoiceItem`
(billing) via the compliance hook — never imports billing's workflow
or router modules.

## Permissions

`india_gst.settings.read`, `india_gst.settings.configure`,
`india_gst.catalog.manage`, `india_gst.reports.read`.
`settings.read` is granted to every clinical role — the invoice
form/detail panels call tax-preview and e-invoice status
mid-invoicing, so any role that can touch invoices needs it.

Editing GST fields on a *draft* invoice reuses billing's own
`billing.write`: the operation IS invoice editing, and a module-own
permission would drift out of sync with billing's role grants
(cross-module gating precedent: agenda → clinical_notes).

## Tools exposed

None (`get_tools()` → `[]`), same as verifactu.

## Events emitted

None in v1 — GST compliance data is written synchronously via
`BillingComplianceHook`, not the event bus (see Gotchas).

## Events consumed

None in v1.

## Lifecycle

- `installable=True`, `auto_install=False` (activated from admin UI),
  `removable=True`.
- `install()` only registers the compliance hook — it must NEVER touch
  clinic data (the original PR seeded demo data into real clinics from
  here; that entire path was removed in the fix-up). Configuration is
  UI-driven: the settings auto-configure action creates SAC defaults
  and the `GST 18%` VatType idempotently.
- `uninstall()` blocks if **any** `IndiaGstInvoiceItem` is linked to a
  non-draft invoice (issued/partial/paid/credit-note) — the module
  owns tax-split data needed to render/audit any issued invoice.
- Migrations on the `india_gst` Alembic branch (`igst_0001`).

## Demo data

`install()` never seeds clinic data (see Lifecycle above) — all India
GST demo fixtures live in the host app's `scripts/seed_demo.py` /
`app/seeds/demo_data.py`, gated so they never run against a real
tenant:

- `./scripts/seed-demo.sh --lang ta` and
  `./scripts/seed-demo.sh --lang en --country in` both seed a GST-ready
  clinic (Chennai, GSTIN `33ABCDE1234F1Z7`, `clinic_state="33"`) and 7
  invoices — 4 intra-state (CGST+SGST) and 2 inter-state (IGST), plus 1
  draft with only `place_of_supply` pre-filled.
- `seed_demo.py::seed_india_gst_invoice_breakdown()` runs the real
  `IndiaGstHook.on_invoice_issued` against each seeded non-draft
  invoice — the exact method billing calls at actual issue time — so
  the tax split, SAC snapshot, and FY document number are never
  duplicated in the seed script.
- `demo_data.py::is_india_demo()` (`LANG == "ta" or COUNTRY == "in"`)
  is the single switch that activates `clinic.settings.country = "IN"`
  for the seed. `--country in` is only accepted with `--lang en`
  (`--lang ta` already implies it) — `main()` exits with an error for
  other `--lang` values.
- `--lang en --country in` reuses the same 15 patient "characters" as
  `--lang ta`, transliterated from Tamil script to Latin script
  (`INDIA_PATIENT_NAMES` in `demo_data.py`), including emergency
  contacts — deliberately not the default English demo's American
  names, since GST invoices next to American names read wrong. Clinic
  staff names are unaffected.
- Both variants gate on the module actually being installed
  (`_module_is_installed(db, "india_gst")`) — seeding never installs
  the module itself. Full walkthrough: `docs/modules/india_gst.md` §3.5.

## Gotchas / non-obvious invariants

- **GSTIN has two owners.** `IndiaGstSettings.gstin` is the clinic's
  own (supplier) GSTIN. `Invoice.billing_tax_id` (billing-owned,
  generic) is the *recipient's* GSTIN. Never conflate them.
- **Tax math never recomputes — it splits.** `compute_gst_breakdown`
  divides each line's already-computed `InvoiceItem.line_tax` into
  CGST+SGST or IGST. CGST and SGST are always **equal** (each =
  line tax / 2, rounded HALF_UP per head — GSTR-1 reconciliation
  rejects asymmetric heads); odd-paise lines may drift ±0.01 vs
  `line_tax`, which is expected head-wise rounding. Sign-agnostic, so
  credit-note amounts (already negative — billing negates `unit_price`
  once in `create_credit_note`) split correctly without re-negation.
- **GST document numbers come from the module's own FY counter**
  (`india_gst_document_sequences`, one row per clinic+prefix+FY,
  `SELECT … FOR UPDATE`, unique constraint). NEVER derive them from
  billing's `sequential_number`: that series resets on the calendar
  year and repeats within a financial year between January and March.
  Idempotent re-issue reuses the number already in the snapshot.
- **`Invoice.compliance_data` is a plain JSONB column, not
  `MutableDict`.** SQLAlchemy only detects a change on reassignment,
  never on in-place mutation. Billing's own
  `invoice.compliance_data.update(...)` merge in
  `InvoiceWorkflowService.issue_invoice` is a same-object no-op
  whenever `compliance_data` was already non-empty — which it always is
  here, since the draft-time PUT endpoint pre-populates
  `compliance_data['IN']['place_of_supply']`. `hook.py::_apply`
  therefore reassigns `invoice.compliance_data` to a **new** dict
  itself before returning, rather than trusting the caller's merge.
- **Historical snapshot, not live settings.** At issue time the hook
  writes supplier/recipient/place-of-supply into
  `compliance_data['IN']` — later edits to `IndiaGstSettings` never
  change how an already-issued invoice renders.
- **Credit notes inherit place of supply from the original invoice**,
  not their own `compliance_data` (they have none until issued) — see
  `hook.py::_apply`'s `source_for_place_of_supply`.
- **Only `registration_type == "regular"` computes GST.**
  Composition/Unregistered/Exempt are stored but the hook returns `{}`
  (no GST rows) — Composition-scheme rules are materially different
  and out of scope for v1.
- **E-invoice tracks applicability only.** No live GSP/IRP provider is
  wired in; the retry endpoint always returns `409` — never a fake
  success. State is `not_required` (below the turnover threshold) or
  `not_configured` (above it). Provider adapters, queues and IRN
  columns arrive together with a real integration, not before.
- **State codes, never display strings.** `clinic_state`/
  `place_of_supply` are always the 2-digit codes from `constants.py`
  (`INDIA_STATES`), compared directly — never free-text names.
- **HTTPException `detail` must be a plain string.** The app's global
  handler (`app/main.py::http_exception_handler`) does `str(exc.detail)`
  — passing a dict silently becomes an ugly Python repr, not JSON.

## Frontend

- **Composables**: `useIndiaGst` (API client), `useIndiaGstStates`
  (state code/name mapping).
- **Components**: `IndiaGstBadge`, `IndiaGstInvoicePanel`,
  `IndiaGstInvoiceFormPanel`, `IndiaGstListFilter`,
  `IndiaGstUnregisteredBanner`, `IndiaGstSettingsCardsSlot` (prefixed —
  verifactu registers its own `SettingsCardsSlot` auto-import name).
- **Pages**: `/reports/india-gst`, `/settings/india-gst`. Both are
  permission-gated with `usePermissions().can()`; the CSV export uses
  an authenticated blob fetch (JWT in header — `window.open` gets 401).
- **i18n**: en, es, fr, pt, ta (`frontend/i18n/locales/`), matching the
  host's five locales.
- **Utils**: `gstBadgeLogic.ts` — pure logic extracted from badge/panel
  components for unit testing (badge color/label, e-invoice color/label,
  Indian clinic detection).
- **Invoice screens**: integration is 100% slot-based
  (`plugins/slots.client.ts`); billing pages carry no india_gst
  conditionals or i18n keys.
- **PDF**: `enhance_pdf_data` provides `label_overrides` ("GST" instead
  of "VAT"/"Tax") and a **structured** `compliance_section` dict
  (title/rows/hint) that billing renders and escapes — never HTML
  across the module boundary. Tamil locale (`ta`) supported with
  `Noto Sans Tamil` font.

## Tests

- **Backend**: `tests/modules/india_gst/` — GST calculator, hook issue,
  credit-note hook, FY sequence, multi-tenant isolation, permission
  matrix, PDF escaping, uninstall guard/roundtrip, settings router,
  tax preview, reports, e-invoice retry.
- **Frontend**: `frontend/tests/india_gst/` — `useIndiaGstStates`
  (state mapping), `gstBadgeLogic` (badge/panel pure logic).

## Related ADRs

- `docs/adr/0001-modular-plugin-architecture.md` — module boundary.
- `docs/adr/0003-event-bus-over-direct-imports.md` — why this module
  uses the synchronous compliance hook instead, same exception as
  verifactu.

## Documentation

- `docs/modules/india_gst.md` — full installation & operation manual.

## CHANGELOG

See `./CHANGELOG.md`.
