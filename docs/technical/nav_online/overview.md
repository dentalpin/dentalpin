---
module: nav_online
last_verified_commit: 0000000
---

# nav_online — overview

NAV Online Számla real-time invoice reporting for Hungarian clinics
(issue #341). Official module, installable/removable, country `HU` on the
`BillingComplianceHook` seam.

Issued invoices and credit notes are snapshotted as Online Számla 3.0
`InvoiceData` XML into a queue at issue time (no network in the request);
a scheduled worker exchanges a token, submits `manageInvoice` operations
and polls `queryTransactionStatus` until NAV reports DONE or ABORTED.
Sandbox (`test`) and production environments; technical-user credentials
encrypted at rest.

Deep-dive: `docs/modules/nav_online.md`. Module notes: the module
`CLAUDE.md`.
