# NAV Online Számla (nav_online)

Hungarian practices must report every issued invoice to NAV's Online
Számla system in real time (Online Számla 3.0 API, mandatory since 2021).
This module does that on the billing compliance seam — the same pattern
as Veri*Factu (ES) and India GST.

## 1. What a clinic needs before enabling

1. A **technical user** created on the Online Számla portal for the
   clinic's adószám: login, password, **signature key** (aláírókulcs) and
   **exchange key** (cserekulcs, exactly 16 characters).
2. The clinic's **tax number** on the clinic profile (8-digit törzsszám or
   the full 11-digit `12345678-2-41`).
3. The invoice currency must be **HUF** (phase 1).
4. A `softwareId` — NAV requires the reporting software to be identified;
   the default `DENTALPIN-00000001` is a placeholder the operator replaces
   with the id registered for their deployment.

Settings → Billing → *NAV Online Számla*: enter the above, **Test
connection** (a live `tokenExchange` against the selected environment),
then **Enable reporting**. Start on `test` (api-test.onlineszamla.nav.gov.hu)
and switch to `prod` once submissions come back DONE.

## 2. What gets reported

| Event | NAV operation | Notes |
|---|---|---|
| invoice issued | `CREATE` | full `InvoiceData`, `completenessIndicator=false` |
| credit note cancelling what is left of the invoice | `STORNO` | references the original number, negative lines |
| partial credit note | `MODIFY` | same document; the invoice keeps a balance on NAV's books |

A credit note is a modification document of its invoice. Its
`invoiceReference` carries `modificationIndex` = 1 for the first credit
note of that invoice, 2 for the second, and so on; every line carries a
`lineModificationReference` whose `lineNumberReference` continues the
numbering after the invoice's own lines and those of earlier credit notes
(`lineOperation` `CREATE`), as in NAV's *Módosítás és érvénytelenítés*
samples. The chain is read from the module's own submission log: a credit
note that brings the invoice's reported gross to zero is a `STORNO`, any
other is a `MODIFY`.

VAT mapping per line: `vat_rate > 0` → `vatPercentage` (e.g. `0.27`);
`0` → `vatExemption` case `TAM` with the line's exemption reason (default
"Áfa tv. 85. § (1) b) — humán-egészségügyi szolgáltatás"). Customers
without an adószám are `PRIVATE_PERSON`; with one, `DOMESTIC`.

## 3. Following submissions

Settings → Billing → *NAV submissions* lists every record with its state:
`pending → sending → sent → done | rejected`; `failed` (transport, retried
automatically with backoff) and `aborted` (gave up). Rejections show NAV's
validation code and message; fix the invoice and **Retry**. **Process
now** runs the worker immediately instead of waiting for the 60 s tick.

## 4. Out of scope (phase 2+)

MODIFY after editing an issued invoice in place, batching up to 100
operations per request, EKÁER, online pénztárgép, non-HUF invoices with
exchange rates, `queryInvoiceData` reconciliation.
