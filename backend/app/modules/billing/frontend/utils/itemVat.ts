import type { VatType } from '~~/app/types'

/**
 * The VAT type a new line starts with: the treatment's own, the clinic's
 * default only when it has none (#1028). The seeded default is exempt, so
 * defaulting for every treatment invoiced 21% items without VAT.
 */
export function lineVatTypeId(
  item: { vat_type_id?: string | null },
  vatTypes: Pick<VatType, 'id' | 'is_default'>[]
): string | undefined {
  const own = vatTypes.find(v => v.id === item.vat_type_id)
  return (own ?? vatTypes.find(v => v.is_default))?.id
}
