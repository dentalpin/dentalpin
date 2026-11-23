import { describe, expect, it } from 'vitest'
import { lineVatTypeId } from '../../../backend/app/modules/billing/frontend/utils/itemVat'

const vatTypes = [{ id: 'exempt', is_default: true }, { id: 'standard', is_default: false }]

describe('lineVatTypeId (#1028)', () => {
  it('takes the treatment\'s own VAT type', () => {
    expect(lineVatTypeId({ vat_type_id: 'standard' }, vatTypes)).toBe('standard')
  })

  it('falls back to the default without one, or with one no longer offered', () => {
    expect(lineVatTypeId({}, vatTypes)).toBe('exempt')
    expect(lineVatTypeId({ vat_type_id: 'deactivated' }, vatTypes)).toBe('exempt')
  })
})
