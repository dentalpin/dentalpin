# Changelog — nav_online module

## Unreleased

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
