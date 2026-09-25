# treasury — overview

Cash/bank accounts, transfers between them, and manual corrections —
where the money sits (expenses tracks where it went). Balances are
always derived from the signed entry ledger, never stored.

Payment and expense auto-posting is explicitly later work with its own
design; this module never writes into other modules' tables.
