# Changelog — sdi_it

## 0.1.0 (2026-09-07) — phase 1

- FatturaPA `FPR12` builder (TD01/TD04, `Natura N4` exempt lines, bollo
  virtuale, recipient routing) validated against the official XSD.
- `BillingComplianceHook` for `IT` with the B2B gate: only invoices to a
  valid partita IVA become SDI records; patient invoices are marked
  `not_applicable` (art. 10-bis DL 119/2018, ADR 0025).
- Manual transport: XML download, mark exported, receipt import (RC/NS/MC),
  requeue after a scarto with the same number and date; billing's
  edit-billing-party flow is allowed while the latest record is `rejected`
  and queues the corrected file.
- Tables `sdi_it_settings`, `sdi_it_records` on the `sdi_it` Alembic branch.
