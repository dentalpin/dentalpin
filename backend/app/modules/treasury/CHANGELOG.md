# Changelog — treasury

## Unreleased

- Follow-up: fold `tre_0002_created_by` + `tre_0003_entry_guards`
  back into `tre_0001` (single-release module, agreed on #463);
  dev DBs that applied them must re-stamp the branch.
- Follow-up round 2: Correct modal labels the memo as required
  (`correctMemo`, per locale); new accounts accept an opening
  balance; accounts deactivate/reactivate from the statement header
  (PATCH `is_active`, reversible).
- Follow-up: Correct button stays disabled until the memo is filled
  (memo is required there); header buttons wrap on narrow screens;
  transfer selects show placeholders; `normAmount` parses full
  Spanish amounts (`1.234,50` → `1234.50`).
- Maintainer round 4: `fail()` reads the API `message` envelope via
  `errorDetail()`; nav self-places under `financials`; events.md +
  CLAUDE.md document `treasury.transferred` / `treasury.corrected`
  (DELETE is 409, not cascade); POST /transfers answers 201;
  future-dated movements are 422; transfer selects list active
  accounts only; amounts accept `25,50`; statement rows show date +
  signed out-legs; negative balances render red (warning, never block).
- `created_by` on every entry (nullable column, folded into
  `tre_0001`) + `treasury.transferred` / `treasury.corrected` events;
  accounts with ledger entries refuse DELETE with 409 (deactivate
  instead); table-level kind/amount guards (folded into `tre_0001`);
  decimal edges are 422.
- Round 2: single-query balances (no N+1), single error toast
  (`errorToast: false`), transfers/corrections refuse deactivated
  accounts (422), naive datetimes are clinic-local wall clock.

- Initial module: cash/bank accounts, paired transfers, manual
  corrections with required memos, derived balances, treasury page.
  Later (own design): payment/expense auto-posting, overdraft guards.
- Fix composable import depth in `pages/treasury/index.vue` (`../` →
  `../../`, TS2307 in CI frontend-typecheck) and stamp real
  `last_verified_commit` in the en/es screen docs.
