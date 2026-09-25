# treasury module

Cash/bank accounts, transfers, and manual corrections — where the money
sits (expenses tracks where it went).

## Public API

Routes mounted at `/api/v1/treasury/` (admin only, payroll-grade blast
radius until clinics widen grants via roles).

- `GET    /accounts` — list with derived balances; `treasury.read`
- `POST   /accounts` — create (409 on duplicate name); `treasury.write`
- `PATCH  /accounts/{id}` — rename/deactivate (all-optional + `exclude_unset`); `treasury.write`
- `DELETE /accounts/{id}` — delete only when the account has no entries (409 otherwise, deactivate instead); `treasury.write`
- `GET    /accounts/{id}/entries` — statement; `treasury.read`
- `POST   /transfers` — paired legs, same group; `treasury.write`
- `POST   /accounts/{id}/corrections` — manual adjustment, memo required; `treasury.write`

409s come from UNIQUE constraints, never select-then-insert (L6).

## Events published

- `treasury.transferred` on every transfer — payload: `clinic_id`,
  `group_id` (shared by both legs), `from_account_id`,
  `to_account_id`, `amount`, `created_by` (nullable). Consumed by
  `activity_journal`.
- `treasury.corrected` on every manual correction — payload:
  `clinic_id`, `account_id`, `entry_id`, `amount`, `direction`
  (`in`/`out`), `memo`, `created_by` (nullable). Consumed by
  `activity_journal`.

## Data model

`treasury_accounts` (name unique per clinic, kind cash|bank,
opening balance, active flag) + `treasury_entries` (append-only signed
legs: transfer_out/transfer_in/correction_in/correction_out/opening).
Balances are always derived (opening + signed entries), never stored.

## Dependencies

None (core only). Payment/expense auto-posting explicitly Later.

## Permissions

`treasury.read`, `treasury.write`, granted to `admin` (`*`) only.

## Frontend

`pages/treasury/index.vue` — accounts, transfer modal, statement.

## Later (out of scope, needs its own design)

- Payment/expense auto-posting (touches money write paths).
- Overdraft guard (negative balances show a red warning in v1, never block).
- Multi-currency accounts.
- Recurring transfers.

## Lifecycle

- `installable=True`, `auto_install=False`, `removable=True`.
- Own Alembic branch (`treasury`, `tre_0001`).

## CHANGELOG

See `./CHANGELOG.md`.
