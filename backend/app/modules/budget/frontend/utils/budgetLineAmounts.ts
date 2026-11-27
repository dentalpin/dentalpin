/**
 * Line amounts as `BudgetItemService._calculate_line_totals` computes them
 * (#1235): a percentage discount of the line, or an absolute discount capped
 * at the line subtotal, comes off before the VAT of the item's VAT type.
 * Each amount is rounded to cents half away from zero, like the backend's
 * Numeric(10, 2) columns; the total is rounded from the unrounded
 * taxable + tax, as the backend stores it.
 *
 * Billing has the same arithmetic for invoice lines (`lineAmounts`, #1032),
 * but budget does not depend on billing, so it keeps its own copy of this
 * small helper. Keep the two in step with their services.
 */
export interface BudgetLineInput {
  unit_price: number | string
  quantity?: number | null
  discount_type?: string | null
  discount_value?: number | null
}

export interface BudgetLineAmounts {
  subtotal: number
  discount: number
  tax: number
  total: number
}

function cents(value: number): number {
  // toPrecision drops float noise (100 * 1.005 = 100.49999...) before rounding.
  const scaled = Number((Math.abs(value) * 100).toPrecision(12))
  return (Math.sign(value) * Math.round(scaled)) / 100 || 0
}

export function budgetLineAmounts(line: BudgetLineInput, vatRate: number): BudgetLineAmounts {
  const subtotal = Number(line.unit_price || 0) * (line.quantity || 1)
  const value = Number(line.discount_value || 0)
  let discount = 0
  if (line.discount_type && value) {
    discount = line.discount_type === 'percentage'
      ? (subtotal * value) / 100
      : Math.min(value, subtotal)
  }
  const taxable = subtotal - discount
  const tax = (taxable * (vatRate || 0)) / 100
  return {
    subtotal: cents(subtotal),
    discount: cents(discount),
    tax: cents(tax),
    total: cents(taxable + tax)
  }
}
