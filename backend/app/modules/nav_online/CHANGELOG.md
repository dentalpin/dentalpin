# Changelog — nav_online module

## Unreleased

- fix(#779): the fallback `issue_date` of a queued record is the clinic's day, not the server's UTC day.
- fix(#768): every `SELECT … FOR UPDATE` in this module now re-reads the locked row (`populate_existing`). A locking select on a row already in the session returned the cached instance with its pre-lock values. A guard test now enforces this across the tree.

- fix(#743): emptying the tax number, technical user login or developer contact in the settings now clears it. The page sent `null`, and the router skipped every `null` as "not sent", so the old value came back. A save that would leave an enabled clinic without complete credentials now answers 400. Before, that was checked only when enabling.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).

- feat(i18n): Arabic (`ar`) locale for the module's frontend layer.
- fix: the records-page state filter's 'all states' option used `''` as its value, which reka-ui rejects in `<SelectItem />`; it now uses `null`.

- feat(#341): initial release — phase 1 of NAV Online Számla reporting:
  `BillingComplianceHook` for HU snapshotting issued invoices / credit
  notes as Online Számla 3.0 `InvoiceData` XML (TAM exemption + 27 %
  lines, PRIVATE_PERSON/DOMESTIC customers, STORNO), a queued worker
  doing tokenExchange → manageInvoice → queryTransactionStatus with
  backoff and retry, test/prod environments, settings + records pages.
- fix: `InvoiceData` lines carry the mandatory `lineExpressionIndicator`
  (+ `lineNatureIndicator` SERVICE) and report the net **after** the
  line discount; bare 8-digit adószám no longer invents vatCode/countyCode.
- fix: `login`/`softwareDevContact` are XML-escaped in the envelope;
  retry also accepts rows stuck in `sending`; uninstall refuses while
  records reported to NAV (`sent`/`done`) exist, like verifactu.
