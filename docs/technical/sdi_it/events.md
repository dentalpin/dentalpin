---
module: sdi_it
last_verified_commit: 0000000
---

# sdi_it — events

This module neither publishes nor subscribes to bus events in phase 1.
It is driven by the billing compliance hook (`on_invoice_issued` /
`on_credit_note_issued` / `regenerate_after_party_change`).
