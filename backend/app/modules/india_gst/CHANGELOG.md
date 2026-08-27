# Changelog — india_gst module

## Unreleased

- feat(#144, #132): Polish (pl) and Italian (it) locales for the module's frontend layer.

- feat(#262): GSTIN validation verifies the 15th-character mod-36 check digit (`gstin_checksum_char`) on top of the CBIC format regex — typos are rejected at the settings PUT with the expected digit named. The settings response gains `gstin_state_mismatch` (GSTIN's leading state code vs `clinic_state` — warn, never block) and the settings screen shows a live hint; the fixture/demo GSTINs were checksum-corrected (`…1Z5→…1Z7`, `…9Z9→…9ZW`, `…1Z6→…1ZC`, `…1Z3→…1Z4`).
- feat(#131): German (de) locale for the module's frontend layer.

### Demo fixtures: native Indian patient names for the English variant

- **Added**: `--lang en --country in` now seeds native Indian (Romanized)
  patient names, emergency-contact names, phone numbers, and emails
  instead of the default English demo's American ones — the India GST
  module is meant for Indian clinics, so American names next to a GSTIN
  and CGST/SGST breakdown read wrong. `INDIA_PATIENT_NAMES` in
  `demo_data.py` gives each of the 15 patients the same identity as
  their `ta` (Tamil-script) counterpart, transliterated to Latin script;
  `get_patients_data()` reuses the Tamil demo's phone/email values
  verbatim (already plain digits / Romanized strings). Clinic staff
  (admin/dentist/hygienist/assistant/receptionist) are unchanged — out
  of scope for this pass.

### Demo fixtures: English-language India GST variant

- **Added**: `scripts/seed_demo.py --lang en --country in` seeds the same
  India GST clinic/invoice fixtures as `--lang ta` (Chennai, GSTIN,
  4 intra-state CGST/SGST + 2 inter-state IGST invoices) but with English
  UI text, for users who want an India demo without the Tamil locale.
  `demo_data.py` gains a `COUNTRY` toggle (`set_country()`,
  `is_india_demo()`) orthogonal to `LANG` — `--lang ta` still implies
  India on its own; `--country in` is currently only accepted with
  `--lang en` (validated in `main()`; `--lang ta` already implies it).
  Default `--lang en` (no `--country`) is unchanged — still the USA/USD
  demo clinic.

### Demo fixtures: CGST/SGST/IGST breakdown on seeded invoices

- **Fixed**: the Tamil demo (`--lang ta`) previously only created
  `IndiaGstSettings`/`GST 18%`/SAC defaults — seeded invoices were
  inserted directly into the DB, bypassing `IndiaGstHook` entirely, so
  every issued/paid/partial invoice had `compliance_data IS NULL` and
  no CGST/SGST/IGST split. `scripts/seed_demo.py` now runs the real
  `IndiaGstHook.on_invoice_issued` (same method billing calls at
  actual issue time) against each non-draft seeded invoice, after
  pre-filling `compliance_data['IN']['place_of_supply']` on the
  invoice dict in `demo_data.py`. No tax logic is duplicated — the
  hook is the sole author of the CGST/SGST/IGST split, SAC snapshot,
  and FY-scoped GST document number.
- **Fixtures**: of the 7 seeded Tamil invoices, 4 are intra-state
  (Tamil Nadu, `33` → CGST+SGST) and 2 are inter-state (Karnataka `29`
  and Maharashtra `27`, both with a structurally valid recipient
  GSTIN → IGST); the draft invoice keeps only its pre-filled place of
  supply, matching what an actual draft looks like before issue.

### Real-world GST validation pass (tresundios, post fix-up)

- **Fixed**: e-invoice applicability compared a single invoice's
  `total` against `turnover_threshold` — the statutory trigger is
  aggregate annual turnover (PAN-wide across relevant GSTINs), not a
  per-invoice amount. `einvoice_state` now derives from whether the
  clinic has declared a `turnover_threshold` at all (`not_configured`)
  vs not (`not_required`), never from the invoice being issued. Hint
  text on the invoice PDF updated to match.
- **Tests**: interstate credit-note regime preservation, missing
  `clinic_state` issue-block, e-invoice applicability (turnover vs
  invoice amount), CSV formula-injection neutralization, auto-configure
  `GST 18%` VAT-type idempotency and tenant scoping, cross-clinic FY
  counter independence, and a repeated-allocation test proving the
  `SELECT … FOR UPDATE` counter lock never drops or repeats a serial.
- **Demo fixtures**: added an explicit, isolated `seed_india_gst()` step
  to `scripts/seed_demo.py` (Tamil Nadu clinic, GSTIN
  `33ABCDE1234F1Z5` — structurally valid per the CBIC format regex,
  labelled test/demo data, not a real taxpayer's registration) that
  only runs for `--lang ta` and only when `india_gst` is already
  installed. `demo_data.py` sets `country=IN` on the Tamil clinic so
  the hook activates for it. Neither path runs from module install,
  auto-install, or any production tenant lifecycle.
- **Docs**: GSTIN validation clarified as format-only (no mod-36
  checksum); manual validation checklist and expanded CA-confirmation
  guidance for CGST/SGST rounding, FY numbering convention, and
  turnover-based e-invoice applicability added to
  `docs/modules/india_gst.md`.

### Maintainer fix-up on top of PR #210

- **Lifecycle made safe**: `install()` no longer runs any seed against
  real clinics (it used to overwrite `trade_name`, stamp a placeholder
  GSTIN, re-tax issued invoices and create fake invoices); it only
  registers the compliance hook. `uninstall()` keeps the guard and
  unregisters — no destructive cleanup. `seed.py` deleted; the
  `GST 18%` VatType get-or-create moved to the auto-configure endpoint.
- **FY-scoped numbering**: new `india_gst_document_sequences` counter
  (unique per clinic+prefix+FY, `SELECT … FOR UPDATE`). Numbers no
  longer derive from billing's calendar-year `sequential_number`, which
  duplicated GST serials between January and March.
- **Multi-tenancy**: added the missing `clinic_id` filter to 7 queries
  (hook, draft-update endpoint, reports/CSV);
  `UNIQUE(clinic_id, catalog_item_id)` on SAC defaults.
- **PDF contract hardened**: the hook now hands billing a structured
  `compliance_section` dict which billing renders and escapes —
  removes an HTML-injection vector via GSTIN/trade-name values.
- **CGST = SGST**: equal halves rounded HALF_UP per head (was
  remainder-absorption, which produced asymmetric heads GSTR-1
  reconciliation rejects).
- `validate_before_issue` requires `clinic_state` for regular
  registrants (missing state silently taxed everything as IGST).
- Role grants: `settings.read` for all clinical roles (invoice panels
  call tax-preview/e-invoice status); reports/settings pages
  permission-gated in the UI; CSV export via authenticated fetch.
- Dead e-invoice scaffolding deleted (provider ABC, submission queue,
  never-written IRN/ack columns, logo storage, inert `rounding_rule`).
  Retry still honestly answers `409`.
- Reports: SQL pagination + `PaginatedApiResponse`, typed date params
  (422 on malformed), CSV formula-injection guard.
- i18n: fr/pt locales added (host declares five).
- Tests: multi-tenant isolation, role permission matrix, PDF escaping,
  FY sequence continuity/reset.

### Original PR #210 (tresundios)

- PDF invoice integration: `enhance_pdf_data` provides a GST breakdown
  section with document number, place of supply, supplier/recipient
  GSTINs, and CGST/SGST/IGST totals. Label overrides replace
  "VAT"/"Tax" with "GST" for Indian clinics.
- Tamil locale (`ta`) support in PDF generation — Tamil labels and
  `Noto Sans Tamil` font in the CSS font-family stack.
- Uninstall guard: blocks uninstall if any non-draft invoice has GST
  line-item data, preventing orphaned CGST/SGST/IGST breakdowns.
- Frontend tests: `useIndiaGstStates` and `gstBadgeLogic` unit tests
  (50 tests covering state mapping, badge logic, e-invoice labels).
- Full module documentation: `docs/modules/india_gst.md`.
- Settings page: one-click **Auto-configure** assigns the default dental SAC
  (`999312`) to every treatment still missing one
  (`POST /catalog-defaults/autoconfigure`). Additive only — an existing
  default is never overwritten, so it is safe to re-run.
- Fixed: the missing-SAC list rendered treatment names in Spanish
  regardless of the viewer's language. `GET /catalog-defaults` now returns
  the whole `names` translation dict and the page resolves it against the
  active UI locale (English fallback).
- Initial implementation: CGST/SGST/IGST tax-split engine, GSTIN capture
  (supplier via `IndiaGstSettings`, recipient via billing's
  `Invoice.billing_tax_id`), place-of-supply-driven intra/inter-state
  determination, SAC code defaults per treatment catalog item, credit-note
  reversal (inherits place of supply from the original invoice), FY-scoped
  GST document numbering (April–March), and a GST reconciliation report
  with CSV export.
- E-invoice applicability tracking (`not_required`/`not_configured`
  per invoice), no live GSP/IRP provider — the retry endpoint always
  returns `409`, never a fabricated success.
- `BillingComplianceHook` implementation (`country_code="IN"`), mirroring
  the `verifactu` module's architecture: country-gated, no billing schema
  changes, extends via `Invoice.compliance_data['IN']`.
- Only `registration_type == "regular"` drives invoicing logic in v1;
  Composition/Unregistered/Exempt are stored settings with no tax
  calculation (documented limitation).

## 0.1.0 — 2026-08-19

- Initial release.
