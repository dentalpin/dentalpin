# sdi_it — module conventions

- **Scope rule first.** Only invoices whose `billing_tax_id` is a valid
  partita IVA produce an SDI record (`services/tax_ids.is_business_recipient`).
  Never widen this: healthcare invoices to natural persons may not be
  electronic (art. 10-bis DL 119/2018, ADR 0025). Patient invoices are the
  Sistema TS module's business (ADR 0026).
- **No columns in `billing`.** Everything lives in `sdi_it_*`; the hook
  returns its data through `Invoice.compliance_data["IT"]`.
- **XML is built at issue time** (`hook.build_record`) and stored verbatim;
  receipts are stored verbatim too. Regeneration only after a scarto
  (`requeue` endpoint, or billing's edit-billing-party flow through
  `can_edit_billing_party` / `regenerate_after_party_change`), with the
  same number and date and a new progressivo.
- **Bollo is the issuer's cost.** `DatiBollo` is declared but never added
  to `ImportoTotaleDocumento`: the XML total must equal the invoice total.
- **Schema fidelity.** `tests/modules/sdi_it/test_xml_builder.py` validates
  every generated file against the vendored official XSD; keep that test
  green before touching element order in `services/xml_builder.py`.
- Transport drivers: `manual` (this PR), `pec` (planned). Both feed the
  same record states: `pending → exported → delivered | undeliverable | rejected`.
