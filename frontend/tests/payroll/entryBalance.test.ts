import { describe, expect, it } from 'vitest'
import { amountToCents, entryBalanceIssue } from '../../../backend/app/modules/payroll/frontend/utils/entryBalance'

describe('amountToCents', () => {
  it('reads cents from strings and numbers, ignoring float noise', () => {
    expect(amountToCents('1000.10')).toBe(100010)
    expect(amountToCents(1000.1)).toBe(100010)
    expect(amountToCents('0.500')).toBe(50)
    expect(amountToCents(0.1 + 0.2)).toBe(30)
    expect(amountToCents('42')).toBe(4200)
  })

  it('refuses a third decimal and non-numbers', () => {
    expect(amountToCents('1000.004')).toBeNull()
    expect(amountToCents('0.005')).toBeNull()
    expect(amountToCents('')).toBeNull()
    expect(amountToCents('abc')).toBeNull()
  })
})

describe('entryBalanceIssue (#1138)', () => {
  it('accepts a balanced cents entry', () => {
    expect(entryBalanceIssue('1000.10', '0.5', '999.60')).toBeNull()
    expect(entryBalanceIssue(120.3, 100.1, 20.2)).toBeNull()
  })

  it('flags sub-cent amounts the old 0.005 tolerance let through', () => {
    expect(entryBalanceIssue('1000.004', '0.005', '999.999')).toBe('subCent')
    expect(entryBalanceIssue('100', '0.001', '100')).toBe('subCent')
  })

  it('flags any cent of difference, matching the exact API check', () => {
    expect(entryBalanceIssue('1000', '0', '999.99')).toBe('mismatch')
  })

  it('flags non-numeric input', () => {
    expect(entryBalanceIssue('abc', '0', '0')).toBe('invalid')
  })
})
