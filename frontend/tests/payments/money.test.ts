import { describe, expect, it } from 'vitest'
import { splitBudgetCollection, toCents } from '../../../backend/app/modules/payments/frontend/utils/money'

describe('toCents', () => {
  it('rounds float noise from client-side arithmetic', () => {
    expect(120.3 - 100.1).not.toBe(20.2)
    expect(toCents(120.3 - 100.1)).toBe(20.2)
    expect(toCents(0.1 + 0.2)).toBe(0.3)
    expect(toCents(1.005)).toBe(1.01)
    expect(toCents(42)).toBe(42)
  })
})

describe('splitBudgetCollection', () => {
  it('sends cents only when the amount exceeds the pending balance (#989)', () => {
    const { toBudget, toOnAccount } = splitBudgetCollection(120.3, 100.1)
    expect(toBudget).toBe(100.1)
    expect(toOnAccount).toBe(20.2)
    expect(toCents(toBudget + toOnAccount)).toBe(120.3)
  })

  it('puts everything on the budget when the amount fits', () => {
    expect(splitBudgetCollection(50, 100.1)).toEqual({ toBudget: 50, toOnAccount: 0 })
  })

  it('puts everything on account when nothing is pending', () => {
    expect(splitBudgetCollection(30.33, 0)).toEqual({ toBudget: 0, toOnAccount: 30.33 })
  })
})
