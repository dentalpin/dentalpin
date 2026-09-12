---
module: sdi_it
last_verified_commit: 0000000
---

# sdi_it — technical overview

FatturaPA / SDI e-invoicing for Italian clinics, phase 1 (issue #133,
ADR 0025). Country-gated `BillingComplianceHook` (`IT`) in the
`verifactu` shape: own tables, own Alembic branch (`sdi_it`), nothing
added to `billing`.

## The gate

`services/tax_ids.is_business_recipient(billing_tax_id)`: only a valid
partita IVA makes an invoice an SDI document. Natural persons (codice
fiscale) get `compliance_data["IT"] = {"sdi": "not_applicable",
"reason": "b2c_healthcare_art_10bis"}` and no record — healthcare
invoices to persone fisiche may not be electronic (art. 10-bis DL
119/2018).

## Flow

1. `hook.on_invoice_issued` / `on_credit_note_issued` → `build_record`:
   renders the `FPR12` file (`services/xml_builder.build_fattura`,
   TD01/TD04, `Natura N4` + `RiferimentoNormativo` for exempt lines,
   `DatiBollo` above €77.47, `CodiceDestinatario` from
   `billing_address.sdi_code`/`pec` else `0000000`), bumps the clinic's
   `progressivo_invio`, stores an `sdi_it_records` row in `pending`.
2. Manual transport: `GET /records/{id}/xml` (download),
   `POST /records/{id}/exported` (uploaded to the SDI).
3. `POST /receipts` parses the SDI receipt (`services/receipts`):
   `RC → delivered`, `MC → undeliverable`, `NS → rejected` with the
   error list; the receipt XML and `IdentificativoSdI` are stored.
4. `POST /records/{id}/requeue` after a scarto: same number and date,
   new progressivo, old record kept as history.

## PEC transport (phase 2)

`services/pec_transport.py` (stdlib `smtplib`/`imaplib` in the default
executor, no new dependency): `send_file` attaches the FPR12 to a message
for the SDI mailbox; `poll_receipts` reads unseen messages from
`pec.fatturapa.it`, extracts receipt attachments (XML or inside a zip),
marks them seen and reports the SDI's dedicated reply address.
`services/submission_queue.process_clinic` drains one clinic (rows locked
`FOR UPDATE SKIP LOCKED`, commit before every network call, backoff per
row, clinic paused ten minutes on mailbox errors) and applies receipts via
`services/receipts.apply_receipt`, shared with the API import.
`tasks.py` schedules it every 120 s.

## Frontend layer (phase 3)

`frontend/plugins/settings.client.ts` registers two Settings → Billing
pages (`SdiItSettingsPage.vue`, `SdiItRecordsPage.vue`);
`frontend/plugins/slots.client.ts` mounts `InvoiceSdiSlot.vue` in
`invoice.detail.compliance` and `SdiBadge.vue` in `invoice.list.row.meta`
/ `invoice.detail.header.meta`, gated on the clinic country `IT` or an
`IT` block in `compliance_data`. `composables/useSdiIt.ts` wraps the API;
the XML download uses `useApi().raw` (blob). Permissions in
`frontend/app/config/permissions.ts` → `sdiIt`.

## API surface

- `GET /api/v1/sdi_it/settings`, `PUT /api/v1/sdi_it/settings`
- `GET /api/v1/sdi_it/records`
- `GET /api/v1/sdi_it/records/{record_id}/xml`
- `POST /api/v1/sdi_it/records/{record_id}/exported`
- `POST /api/v1/sdi_it/records/{record_id}/requeue`
- `POST /api/v1/sdi_it/receipts`
- `GET /api/v1/sdi_it/records/by-invoice/{invoice_id}`
- `POST /api/v1/sdi_it/pec/test`
- `POST /api/v1/sdi_it/queue/process-now`

## Tests

`backend/tests/modules/sdi_it/`: tax ids, XML builder validated against
the vendored official XSD (`schemas/`), receipt parsing, hook gate and
credit notes, router lifecycle, Alembic round-trip uninstall.

## Not yet

SdICoop, digital signature, `Allegati`.

## See also

- `docs/modules/sdi_it.md` (user-facing description)
- ADR 0025, ADR 0026 (Sistema Tessera Sanitaria, the B2C half)
- `backend/app/modules/sdi_it/CLAUDE.md`
