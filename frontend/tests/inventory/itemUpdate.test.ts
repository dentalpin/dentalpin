import { describe, expect, it } from 'vitest'
import { itemUpdatePayload } from '../../../backend/app/modules/inventory/frontend/utils/itemUpdate'

describe('itemUpdatePayload (#1050)', () => {
  it('leaves the stock out of an edit that did not touch it', () => {
    const payload = itemUpdatePayload({ notes: 'Shelf B', stock_quantity: 10 }, { stock_quantity: '10.00' })
    expect(payload).toEqual({ notes: 'Shelf B' })
  })

  it('sends a correction the user typed, zero included', () => {
    expect(itemUpdatePayload({ stock_quantity: 0 }, { stock_quantity: '10.00' })).toEqual({ stock_quantity: 0 })
  })
})
