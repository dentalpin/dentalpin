# Changelog — treasury

## Unreleased

- Maintainer round 4: `fail()` reads the API `message` envelope via
  `errorDetail()`; nav self-places under `financials`; events.md +
  CLAUDE.md document `treasury.transferred` / `treasury.corrected`
  (DELETE is 409, not cascade); POST /transfers answers 201;
  future-dated movements are 422; transfer selects list active
  accounts only; amounts accept `25,50`; statement rows show date +
  signed out-legs; negative balances render red (warning, never block).
- `created_by` on every entry (new nullable column, `tre_0002`) +
  `treasury.transferred` / `treasury.corrected` events; accounts with
  ledger entries refuse DELETE with 409 (deactivate instead);
  table-level kind/amount guards (`tre_0003`); decimal edges are 422.
- Round 2: single-query balances (no N+1), single error toast
  (`errorToast: false`), transfers/corrections refuse deactivated
  accounts (422), naive datetimes are clinic-local wall clock.

- Initial module: cash/bank accounts, paired transfers, manual
  corrections with required memos, derived balances, treasury page.
  Later (own design): payment/expense auto-posting, overdraft guards.
- Fix composable import depth in `pages/treasury/index.vue` (`../` →
  `../../`, TS2307 in CI frontend-typecheck) and stamp real
  `last_verified_commit` in the en/es screen docs.
