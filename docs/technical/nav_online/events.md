---
module: nav_online
last_verified_commit: 0000000
---

# nav_online — events

This module neither publishes nor subscribes to bus events in phase 1.
It is driven by the billing compliance hook (`on_invoice_issued` /
`on_credit_note_issued`) and its own scheduled job.
