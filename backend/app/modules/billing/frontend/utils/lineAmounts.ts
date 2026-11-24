/**
 * Line amounts as `InvoiceService.calculate_item_totals` computes them
 * (#1032): the discount (percentage of the line, or an absolute amount capped
 * at the line) comes off before VAT. Each amount is rounded to cents on its
 * own, half away from zero like the backend's Numeric(10, 2) columns, and
 * the invoice totals are the sums of those rounded line amounts.
 */
export interface LineInput {
  unit_price: number
  quantity?: number | null
  discount_type?: string | null
  discount_value?: number | null
}

export interface LineAmounts {
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

export function lineAmounts(line: LineInput, vatRate: number): LineAmounts {
  const subtotal = Number(line.unit_price || 0) * (line.quantity || 1)
  const value = Number(line.discount_value || 0)
  let discount = 0
  if (line.discount_type && value) {
    if (line.discount_type === 'percentage') {
      discount = (subtotal * value) / 100
    } else {
      const capped = Math.min(value, Math.abs(subtotal))
      discount = subtotal < 0 ? -capped : capped
    }
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

export function sumLineAmounts(lines: LineAmounts[]): LineAmounts {
  const sum = lines.reduce(
    (acc, line) => ({
      subtotal: acc.subtotal + line.subtotal,
      discount: acc.discount + line.discount,
      tax: acc.tax + line.tax,
      total: acc.total + line.total
    }),
    { subtotal: 0, discount: 0, tax: 0, total: 0 }
  )
  return {
    subtotal: cents(sum.subtotal),
    discount: cents(sum.discount),
    tax: cents(sum.tax),
    total: cents(sum.total)
  }
}
