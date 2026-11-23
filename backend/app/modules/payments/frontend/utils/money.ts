/**
 * Money helpers for payloads.
 *
 * The API takes amounts in cents only (`decimal_places=2`, #989). Amounts the
 * client *computes* (a difference, a sum) must be rounded before they are
 * sent: in JS floats `120.3 - 100.1` is `20.200000000000003`, which the API
 * now answers with a 422.
 */
export function toCents(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100
}

/**
 * Split a collection on a budget: up to the pending balance goes to the
 * budget, the rest on account. Both parts are in cents and add up to the
 * (rounded) amount.
 */
export function splitBudgetCollection(amount: number, pending: number): { toBudget: number, toOnAccount: number } {
  const total = toCents(amount)
  const toBudget = toCents(Math.min(total, Math.max(0, pending)))
  const toOnAccount = toCents(Math.max(0, total - toBudget))
  return { toBudget, toOnAccount }
}
