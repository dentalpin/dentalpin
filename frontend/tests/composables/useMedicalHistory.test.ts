import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { useMedicalHistory } from '../../../backend/app/modules/patients_clinical/frontend/composables/useMedicalHistory'

/** #1045: the PUT replaces the whole history, so it must only follow a successful load. */
const get = vi.fn()
const put = vi.fn()
const granted = new Set<string>()

mockNuxtImport('useApi', () => () => ({ get, put }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))
mockNuxtImport('usePermissions', () => () => ({ can: (p: string) => granted.has(p) }))

describe('useMedicalHistory', () => {
  beforeEach(() => {
    get.mockReset()
    put.mockReset()
    granted.clear()
    granted.add('patients_clinical.medical.read')
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('does not save over a history it failed to load', async () => {
    get.mockRejectedValue(new Error('timeout'))
    const history = useMedicalHistory(ref('patient-a'))
    await flushPromises()

    expect(await history.saveMedicalHistory()).toBe(false)
    expect(put).not.toHaveBeenCalled()
  })

  it('does not save while the history is still loading', async () => {
    get.mockReturnValue(new Promise(() => {}))
    const history = useMedicalHistory(ref('patient-a'))

    expect(await history.saveMedicalHistory()).toBe(false)
    expect(put).not.toHaveBeenCalled()
  })

  it('does not carry an entry over to the next patient', async () => {
    get.mockRejectedValue(new Error('timeout'))
    const first = useMedicalHistory(ref('patient-a'))
    first.addAllergy({ name: 'Penicillin', severity: 'high' })

    const second = useMedicalHistory(ref('patient-b'))
    expect(second.medicalHistory.value.allergies).toEqual([])
  })

  it('saves the edited copy once loaded', async () => {
    const stored = { allergies: [{ name: 'Latex', severity: 'high' }], medications: [], systemic_diseases: [], surgical_history: [] }
    get.mockResolvedValue({ data: stored })
    put.mockImplementation(async (_url: string, data: unknown) => ({ data }))
    const history = useMedicalHistory(ref('patient-a'))
    await flushPromises()

    const edited = { ...history.medicalHistory.value, allergies: [] }
    expect(await history.saveMedicalHistory(edited)).toBe(true)
    expect(put.mock.calls[0]![1]).toEqual(edited)
  })

  it('does not request the history without medical.read (#1268)', async () => {
    granted.clear()
    const history = useMedicalHistory(ref('patient-a'))
    await flushPromises()

    expect(get).not.toHaveBeenCalled()
    expect(history.isLoaded.value).toBe(false)
  })
})
