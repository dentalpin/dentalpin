# Changelog — treasury

## Unreleased

- Initial module: cash/bank accounts, paired transfers, manual
  corrections with required memos, derived balances, treasury page.
  Later (own design): payment/expense auto-posting, overdraft guards.
- Fix composable import depth in `pages/treasury/index.vue` (`../` →
  `../../`, TS2307 in CI frontend-typecheck) and stamp real
  `last_verified_commit` in the en/es screen docs.
