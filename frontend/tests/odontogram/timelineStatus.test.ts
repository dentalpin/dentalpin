import { describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { useOdontogramTimeline } from '../../../backend/app/modules/odontogram/frontend/composables/useOdontogramTimeline'

const get = vi.fn()
mockNuxtImport('useApi', () => () => ({ get }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

describe('useOdontogramTimeline (#1065)', () => {
  it('maps performed to existing, as the Diagnosis chart does', async () => {
    get.mockResolvedValue({
      data: { teeth: [], treatments: [{ id: 'a', status: 'performed' }, { id: 'b', status: 'planned' }] }
    })
    const timeline = useOdontogramTimeline()
    await timeline.fetchOdontogramAtDate('patient-a', '2026-11-01')

    expect(timeline.historicalTreatments.value.map(t => t.status)).toEqual(['existing', 'planned'])
  })
})
