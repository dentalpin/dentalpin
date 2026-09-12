# sistema_ts — module conventions

- **Scope rule first.** Only invoices to natural persons (no partita IVA in
  `billing_tax_id`) become Sistema TS documents; B2B invoices are `sdi_it`'s.
  Never widen either side (art. 10-bis DL 119/2018, ADRs 0025/0026).
- **No columns in other modules.** Opposition lives in
  `sistema_ts_patient_opposition`, `tipoSpesa` per item in
  `sistema_ts_item_types`; `patients.national_id` is read as the codice
  fiscale, never written.
- **Trigger is payment, found by scanning**, not by event handlers: the
  billing events are published before the request commits, so a handler on
  its own session cannot see the invoice. `services/documents.sync_clinic`
  runs every tick and is idempotent (one `inserimento` per invoice).
- **Opposition is honoured, never a skip**: the document still goes, with
  `flagOpposizione=1` and no `cfCittadino` (spec table 5). Changing it
  after acceptance queues a `variazione`.
- **Encryption**: `pincode`, `cfCittadino`, `cfProprietario` are RSA/PKCS1v15
  with the vendored `certs/SanitelCF.cer` (or the clinic's replacement).
  Keep the kit's SoapUI samples as the reference for element order.
- Request/response XML are stored verbatim on the document row: that is
  the proof (`protocollo`) for ten years.
