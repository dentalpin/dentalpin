---
module: sistema_ts
last_verified_commit: 0000000
---

# sistema_ts — technical overview

Sistema Tessera Sanitaria expense submission for Italian clinics, phase 1
(issue #134, ADR 0026). Country-gated module beside `billing` in the
`verifactu` shape: own tables, own Alembic branch (`sistema_ts`,
`depends_on` billing / patients / catalog heads), nothing added to other
modules. Runs next to `sdi_it` (ADR 0025): that one takes the B2B
invoices, this one the patient invoices.

## Trigger and flow

No `BillingComplianceHook` (the registry holds one hook per country and
the trigger is payment, not issue) and no event handler (billing events
are published before the request commits, so a handler on its own session
would not see the invoice). `services/documents.sync_clinic` runs on
every worker tick and is idempotent:

1. paid invoices to natural persons (`billing_tax_id` is not a partita
   IVA) → `inserimento`;
2. credit notes whose original was accepted → `rimborso`;
3. voided invoices with an accepted `inserimento` → `cancellazione`;
4. `PUT /opposition/{patient}` → `variazione` of the patient's accepted
   documents (`queue_variazioni_for_patient`).

`services/documents.build_request` renders a row into the SOAP request
(`services/xml_builder`, element order from the kit's SoapUI samples,
namespace `http://documentospesap730.sanita.finanze.it`), encrypting
`pincode`, `cfProprietario` and `cfCittadino` with RSA/PKCS1v15 and the
vendored `certs/SanitelCF.cer` (`services/crypto`; a clinic can upload a
replacement). `services/ts_client.send` posts with basic auth to the
test/prod `DocumentoSpesa730pPort` endpoint and parses `esitoChiamata`,
`protocollo` and `listaMessaggi` by local name.
`services/submission_queue.process_clinic` drains one clinic (rows
locked `FOR UPDATE SKIP LOCKED`, commit before every network call,
backoff 2 min → 1 h over eight attempts, credential failure pauses the
clinic ten minutes); `tasks.py` schedules it every 120 s.

## Data

- `sistema_ts_settings` — credentials (Fernet at rest), identity
  (`cf_proprietario`, structure codes, `dispositivo`), default
  `tipoSpesa`, `sync_from`, environment.
- `sistema_ts_documents` — one operation per fiscal document: identity as
  sent, `voci` (JSONB), state, `request_xml` / `response_xml`, `esito`,
  `protocollo`, messages. Kept ten years; accepted rows block uninstall.
- `sistema_ts_patient_opposition` — one row per patient, `revoked_at`.
- `sistema_ts_item_types` — `tipoSpesa` (+ flag) per catalog item.

## Frontend layer (phase 2)

`frontend/plugins/settings.client.ts` registers two Settings → Billing
pages (`SistemaTsSettingsPage.vue`, `SistemaTsDocumentsPage.vue`);
`frontend/plugins/slots.client.ts` mounts `PatientOppositionCard.vue` in
`patient.summary.cards` (renders only for `IT` clinics) and
`InvoiceTsSlot.vue` in `invoice.detail.compliance` (IT clinics, patient
invoices only). `composables/useSistemaTs.ts` wraps the API. Permissions
in `frontend/app/config/permissions.ts` → `sistemaTs`.
## TLS to the test service

`invioSS730pTest.sanita.finanze.it` presents a certificate issued by the
private *Sogei Certification Authority Test* and sends no chain, so the
default certifi bundle rejects it (`CERTIFICATE_VERIFY_FAILED`). Point
`SISTEMA_TS_CA_BUNDLE` at a PEM bundle that includes that CA (download it
from the Sistema TS portal; the kit's `CAAgenziadelleEntrateTest.pem` is the
*signing* CA, not the TLS one). Production chains to a public CA and needs
nothing. The worker surfaces the failure as a `TLS:` error on the document
and the settings page.

## API surface

- `GET /api/v1/sistema_ts/settings`, `PUT /api/v1/sistema_ts/settings`
- `GET /api/v1/sistema_ts/documents`, `GET /api/v1/sistema_ts/documents/by-invoice/{invoice_id}`
- `POST /api/v1/sistema_ts/documents/{document_id}/retry`
- `POST /api/v1/sistema_ts/queue/process-now`
- `GET /api/v1/sistema_ts/opposition/{patient_id}`, `PUT /api/v1/sistema_ts/opposition/{patient_id}`
- `GET /api/v1/sistema_ts/item-types`, `PUT /api/v1/sistema_ts/item-types/{catalog_item_id}`

## Tests

`backend/tests/modules/sistema_ts/`: codice fiscale check character and
partita IVA gate; RSA encryption against the vendored certificate and a
generated one (decrypt round-trip); request shapes against the kit
samples; client parsing (esito 0/1/2, fault, 401); document sync
(grouping, cash → `NO`, B2B skipped, opposition, credit note after
acceptance, void, missing CF, `sync_from`); worker (accepted, rejected,
backoff, credential pause, disabled); router; Alembic round-trip.

## Not yet

Async zip service, receipt PDFs, the AdE notification services.
