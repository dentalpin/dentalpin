/**
 * The PATCH body of the edit form. A stock quantity in it is an absolute
 * set, so it only goes when the user changed it: the row can be minutes
 * old, and resending it undid a colleague's receipt or adjustment (#1050).
 */
export function itemUpdatePayload<T extends { stock_quantity: number }>(
  form: T,
  original: { stock_quantity: string | number }
): Omit<T, 'stock_quantity'> & { stock_quantity?: number } {
  const { stock_quantity, ...fields } = form
  return stock_quantity === Number(original.stock_quantity) ? fields : { ...fields, stock_quantity }
}
