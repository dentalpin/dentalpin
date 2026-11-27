import { afterEach, describe, expect, it } from 'vitest'
import { invoiceDaysOverdue, isInvoiceOverdue } from '../../../backend/app/modules/billing/frontend/utils/invoiceOverdue'

/**
 * #1176: the invoice list's overdue badge read `due_date` as UTC midnight,
 * so west of UTC an invoice turned overdue the evening before. The backend
 * (`due_date < today`) never counts the due date itself as overdue, so the
 * badge must not either, in any zone.
 */
const ZONES = ['America/Mexico_City', 'Europe/Madrid', 'Asia/Kolkata']
const originalTz = process.env.TZ

afterEach(() => {
  process.env.TZ = originalTz
})

const issued = (due_date: string) => ({
  is_historical: false,
  credit_note_for_id: null,
  due_date,
  status: 'issued' as const
})

describe('invoice overdue', () => {
  for (const tz of ZONES) {
    it(`${tz}: the due date itself is not overdue, the next day is`, () => {
      process.env.TZ = tz
      const morning = new Date(2026, 10, 26, 9, 0)
      const evening = new Date(2026, 10, 26, 23, 30)
      expect(isInvoiceOverdue(issued('2026-11-26'), morning)).toBe(false)
      expect(isInvoiceOverdue(issued('2026-11-26'), evening)).toBe(false)
      expect(isInvoiceOverdue(issued('2026-11-27'), evening)).toBe(false)
      expect(isInvoiceOverdue(issued('2026-11-25'), morning)).toBe(true)
      expect(invoiceDaysOverdue(issued('2026-11-25'), morning)).toBe(1)
      expect(invoiceDaysOverdue(issued('2026-11-26'), evening)).toBe(0)
    })
  }

  it('a credit note is never overdue', () => {
    expect(isInvoiceOverdue({ ...issued('2020-01-01'), credit_note_for_id: 'x' }, new Date(2026, 0, 1))).toBe(false)
  })
})
