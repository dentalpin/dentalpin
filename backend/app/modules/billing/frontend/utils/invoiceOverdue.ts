import type { InvoiceListItem } from '~~/app/types'
import { parseDateOnly } from '~~/app/utils/wallClock'

type OverdueFields = Pick<InvoiceListItem, 'is_historical' | 'credit_note_for_id' | 'due_date' | 'status'>

/**
 * Overdue from the day after the due date, like the backend's
 * `overdue_invoice_conditions` (`due_date < today`): the due date itself
 * is not overdue. `due_date` is date-only, read as local midnight (#1176).
 */
export function isInvoiceOverdue(inv: OverdueFields, now: Date = new Date()): boolean {
  // A credit note is never overdue (#1090).
  if (inv.is_historical || inv.credit_note_for_id || !inv.due_date) return false
  if (!['issued', 'partial'].includes(inv.status)) return false
  return parseDateOnly(inv.due_date) < new Date(now.toDateString())
}

/** Whole days past the due date (0 on the due date itself). */
export function invoiceDaysOverdue(inv: Pick<InvoiceListItem, 'due_date'>, now: Date = new Date()): number {
  if (!inv.due_date) return 0
  const ms = new Date(now.toDateString()).getTime() - parseDateOnly(inv.due_date).getTime()
  return Math.max(0, Math.round(ms / (24 * 3600 * 1000)))
}
