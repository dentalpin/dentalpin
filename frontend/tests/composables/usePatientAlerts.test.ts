import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { usePatientAlerts } from '../../../backend/app/modules/patients_clinical/frontend/composables/usePatientAlerts'

/** #1268: the alerts route needs medical.read; useApi toasts every 403 it gets. */
const { get, granted } = vi.hoisted(() => ({ get: vi.fn(), granted: new Set<string>() }))

mockNuxtImport('useApi', () => () => ({ get }))
mockNuxtImport('usePermissions', () => () => ({ can: (p: string) => granted.has(p) }))
mockNuxtImport('useDataBus', () => () => ({ on: vi.fn(), publish: vi.fn() }))

describe('usePatientAlerts', () => {
  beforeEach(() => {
    get.mockReset()
    granted.clear()
  })

  it('does not call the alerts endpoint without medical.read', async () => {
    const { alerts } = usePatientAlerts(ref('patient-a'))
    await flushPromises()

    expect(get).not.toHaveBeenCalled()
    expect(alerts.value).toEqual([])
  })

  it('loads the alerts with medical.read', async () => {
    granted.add('patients_clinical.medical.read')
    const alert = { type: 'allergy', severity: 'critical', title: 'Penicillin' }
    get.mockResolvedValue({ data: { alerts: [alert] } })
    const { alerts } = usePatientAlerts(ref('patient-a'))
    await flushPromises()

    expect(get).toHaveBeenCalledWith('/api/v1/patients_clinical/patients/patient-a/alerts')
    expect(alerts.value).toEqual([alert])
  })
})
