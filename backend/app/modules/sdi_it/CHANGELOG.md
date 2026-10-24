# Changelog — sdi_it

## Unreleased — phase 3

- fix(#768): every `SELECT … FOR UPDATE` in this module now re-reads the locked row (`populate_existing`). A locking select on a row already in the session returned the cached instance with its pre-lock values. A guard test now enforces this across the tree.

- fix(#743): emptying the PEC address, SMTP/IMAP host or SMTP username in the settings now clears it. The page sent `null`, and the router skipped every `null` as "not sent", so the old value came back. A save that would leave an enabled PEC transport without complete credentials now answers 400. Before, that was checked only when enabling.

- fix(#723): the paginated list query now ends its `order_by` on the primary key. Rows that tied on the sort column (same date, name or timestamp) were cut from different orderings on each page, so some appeared twice and others on no page.

- chore(#557): slot/settings permission gates now reference PERMISSIONS constants (no behavior change).
- Nuxt layer: Settings → Billing pages "Electronic invoicing (SDI)"
  (regime, exemption reference, bollo, manual/PEC transport with mailbox
  test) and "SDI files" (states, receipts, download / mark uploaded /
  import receipt / regenerate / send now); SDI panel and chip on the
  invoice page through the billing slots; ten locales.
- `GET /records/by-invoice/{invoice_id}` for the invoice panel.

## Unreleased — phase 2

- PEC transport: the clinic's PEC mailbox sends each FPR12 file to the SDI
  (SMTP) and a worker picks the receipts up (IMAP) every two minutes,
  learning the dedicated `sdiNN@pec.fatturapa.it` reply address; retry with
  backoff per file, ten-minute pause of the clinic on mailbox failures.
- Settings: PEC fields (password encrypted at rest, write-only), `POST
  /pec/test` (SMTP + IMAP login), `POST /queue/process-now`.
- `Imposta` per riepilogo is now base × rate rounded once (SDI check 00421).
- `ProgressivoInvio` counter bumped under a row lock, so two invoices issued
  at the same instant cannot share a file name.
- Records carry `transport` and `message_id`; receipt application shared
  between the API import and the poller.

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
