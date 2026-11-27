import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, describe, expect, it } from 'vitest'
import MonthPickerDropdown from '../../module_layers/recalls/frontend/components/MonthPickerDropdown.vue'

/**
 * #1176: a recall's `due_month` is a date-only `YYYY-MM-01`. Parsed with
 * `new Date(s)` it is UTC midnight, which west of UTC is the last day of
 * the previous month, so the picker labelled March as February.
 */
const TZ = process.env.TZ

afterEach(() => {
  process.env.TZ = TZ
})

describe('MonthPickerDropdown', () => {
  it('labels the stored month west of UTC', async () => {
    process.env.TZ = 'America/Mexico_City'
    const wrapper = await mountSuspended(MonthPickerDropdown, { props: { modelValue: '2027-03-01' } })
    const expected = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'long' }).format(new Date(2027, 2, 1))
    const wrong = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'long' }).format(new Date(2027, 1, 1))
    expect(wrapper.text()).not.toContain(wrong)
    expect(wrapper.text()).toContain(expected)
  })
})
