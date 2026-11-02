# Changelog — sistema_ts

## Unreleased — phase 2

- fix(#779): the settings year counts and the opposition date use the clinic's day, not the server's UTC day.
- fix(#768): every `SELECT … FOR UPDATE` in this module now re-reads the locked row (`populate_existing`). A locking select on a row already in the session returned the cached instance with its pre-lock values. A guard test now enforces this across the tree.

- fix(#743): emptying the username, owner's codice fiscale, regione/ASL/SSA codes or the sync-from date in the settings now clears it. The page sent `null`, and the router skipped every `null` as "not sent", so the old value came back. A save that would leave an enabled clinic without complete credentials now answers 400. Before, that was checked only when enabling.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).
- Nuxt layer: Settings → Billing pages "Sistema Tessera Sanitaria"
  (credentials, certificate upload, identity, year overview with the
  31 January deadline, `tipoSpesa` per catalog item) and "Sistema TS
  submissions" (states, protocollo, retry, send now); opposition card in
  the patient summary; submission panel on the invoice page; ten locales.
- Layer polish: dates through `fmtDate` (deadline, issue date, opposed
  since), opposition card gated by `useClinicCountry`, filter change
  resets the submissions list to page 1.

## 0.1.0 (2026-09-09) — phase 1

- Opposition and item-type endpoints answer 404 for a patient or catalog
  item of another clinic (ownership check before the write).
- `SISTEMA_TS_CA_BUNDLE` for the test service's private Sogei CA; a clear
  `TLS:` error instead of the raw SSL trace.

- Per-clinic Sistema TS credentials (basic auth + RSA-encrypted pincode
  with the SanitelCF certificate), test/prod environments.
- Worker: paid patient invoices → `inserimento`, credit notes →
  `rimborso`, voids → `cancellazione`, opposition changes → `variazione`;
  synchronous SOAP service, backoff, `protocollo` stored with the XML.
- Per-patient opposition table and API; `tipoSpesa` per catalog item.
- Year overview (deadline 31 January, unsent/accepted/rejected counts).
