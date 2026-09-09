# nav_online module

NAV Online Számla (Hungary) real-time invoice reporting — issue #341.
Third application of the `BillingComplianceHook` seam (`verifactu` ES,
`india_gst` IN). Phase 1: CREATE for issued invoices, STORNO for credit
notes, one operation per request, test/prod environments, no MODIFY
chains, no EKÁER.

## Flow

1. `NavOnlineHook.on_invoice_issued` (country `HU`) renders the invoice
   as Online Számla 3.0 `InvoiceData` XML (`services/xml_builder.py`) and
   inserts a `nav_online_records` row in `pending`. **No network in the
   request.** Returns `{"HU": {record_id, operation, state, environment}}`
   for `Invoice.compliance_data`.
2. The scheduled worker (`tasks.py`, every 60 s → `services/submission_queue`)
   drains each enabled clinic: `tokenExchange` → per row `manageInvoice`
   (`pending`/`failed` → `sending` → `sent` with `transaction_id`), then
   `queryTransactionStatus` for `sent` rows until `DONE` → `done` or
   `ABORTED`/ERROR → `rejected`. Transport errors: `failed` + exponential
   backoff to `max_attempts` → `aborted`; a failed `tokenExchange` pauses
   the clinic 10 min (`settings.next_send_after`).
3. Admin fixes the invoice and hits **Retry** (`rejected|failed|aborted`
   → `pending`).

## Public API

Routes at `/api/v1/nav_online/`:

| Method | Path | Auth |
|---|---|---|
| GET/PUT | `/settings` | `nav_online.settings.read` / `.configure` |
| POST | `/settings/test-connection` | `.configure` — live tokenExchange |
| GET | `/records`, `/records/{id}/xml` | `nav_online.records.read` |
| POST | `/records/{id}/retry`, `/queue/process-now` | `nav_online.queue.manage` |

## NAV specifics (services/)

- `crypto.py` — `passwordHash` SHA-512, `requestSignature` SHA3-512 over
  `requestId + yyyyMMddHHmmss + signatureKey [+ per-op SHA3-512(op+base64)]`,
  exchange token = AES-128-ECB(PKCS5) of the base64 `encodedExchangeToken`
  with the 16-char exchange key. Pinned by `test_crypto.py`.
- `xml_builder.py` — `HungarianTaxNumber` (8-digit törzsszám or 11-digit
  adószám → taxpayerId/vatCode/countyCode), `PRIVATE_PERSON` customers by
  default (patients), `DOMESTIC` + `customerVatData` when the billing
  party has an adószám. VAT: `vat_rate > 0` → `vatPercentage`; `0` →
  `vatExemption` case **TAM** (humán-egészségügyi szolgáltatás, Áfa tv.
  85. § (1) b)) with the line's `vat_exempt_reason` or the default text.
  Currency HUF only in phase 1 (`validate_before_issue` blocks others).
- `nav_client.py` — envelopes for `tokenExchange`/`manageInvoice`/
  `queryTransactionStatus` (`OSA/3.0/api` + `NTCA/1.0/common`); `post_xml`
  is the only network call (tests monkeypatch it); lxml response parser.
- `submission_queue.py` — the worker; rows locked `FOR UPDATE SKIP
  LOCKED`, commit before every network call.

## Settings & secrets

`nav_online_settings`: environment, 8/11-digit tax number, technical user
login, password / signature key / exchange key (Fernet at rest via
`app.core.email.encryption`, write-only in the API), `software_id`
(18 chars, registered once at NAV) + developer contact. `enabled` refuses
to flip on without complete credentials.

## Dependencies

`manifest.depends = ["billing"]` — the hook contract and the
`invoice_id` FK (migration `depends_on=("bil_0005",)`).

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`; own Alembic
  branch `nav_online` (`nav_0001`); roundtrip uninstall test.
- Hook registered from `on_activate` (in-memory registry, ADR 0020).

## Gotchas

- **The XML is a snapshot** at issue time; editing an invoice afterwards
  does not re-render it — billing's `regenerate_after_party_change` is a
  phase-2 item (NAV needs a MODIFY operation, not an overwrite).
- **NAV rejects are terminal**; the worker never retries them — the admin
  corrects and retries explicitly. Retry also accepts `sending` rows (a
  worker that died mid-request leaves them there).
- **Uninstall refuses** while any record is `sent`/`done` — the local log
  is the audit trail of what NAV has on file.
- **8-digit adószám** → only `taxpayerId`; `vatCode`/`countyCode` are
  optional in the XSD and must not be guessed.
- **Not tax advice**: the software registration (`softwareId`), the
  technical user and the choice of exemption codes are the clinic's
  accountant's call; the module ships sensible defaults.

## CHANGELOG

See `./CHANGELOG.md`.
