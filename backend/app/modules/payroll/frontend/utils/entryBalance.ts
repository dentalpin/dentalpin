/**
 * Client-side check for a payroll entry, matching the API (#1138).
 *
 * The API takes amounts in cents only and wants `net == gross - deductions`
 * exactly. Comparing JS floats with a tolerance let sub-cent input through
 * (the API then answers 422), so compare whole cents instead.
 */
export type EntryBalanceIssue = 'invalid' | 'subCent' | 'mismatch'

/** Whole cents of an amount, or `null` when it is not a number or has more than two decimals. */
export function amountToCents(value: string | number): number | null {
  if (value === '') return null
  const amount = Number(value)
  if (!Number.isFinite(amount)) return null
  const cents = Math.round(amount * 100)
  // `1000.1 * 100` is `100010.00000000001`: allow float noise, not a third decimal.
  if (Math.abs(amount * 100 - cents) > 1e-6) return null
  return cents
}

export function entryBalanceIssue(
  gross: string | number,
  deductions: string | number,
  net: string | number
): EntryBalanceIssue | null {
  if ([gross, deductions, net].some(v => !Number.isFinite(Number(v)))) return 'invalid'
  const g = amountToCents(gross)
  const d = amountToCents(deductions)
  const n = amountToCents(net)
  if (g === null || d === null || n === null) return 'subCent'
  return n === g - d ? null : 'mismatch'
}
