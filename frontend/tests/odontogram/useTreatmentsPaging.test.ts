import { beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { useTreatments } from '#module-layers/odontogram/frontend/composables/useTreatments'

/**
 * The odontogram chart draws every tooth from `fetchTreatments`, so the
 * list has to be complete. The endpoint pages newest-first (default 50,
 * cap 100); a single request dropped a long-standing patient's oldest
 * rows — the initial charting — off the chart.
 */

const { getMock } = vi.hoisted(() => ({ getMock: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get: getMock }))
mockNuxtImport('useToast', () => () => ({ add: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (k: string) => k }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))

function rows(from: number, count: number) {
  return Array.from({ length: count }, (_, i) => ({ id: `t${from + i}`, status: 'performed' }))
}

describe('useTreatments.fetchTreatments', () => {
  beforeEach(() => {
    getMock.mockReset()
  })

  it('walks every page until the total is reached', async () => {
    getMock
      .mockResolvedValueOnce({ data: rows(0, 100), total: 230 })
      .mockResolvedValueOnce({ data: rows(100, 100), total: 230 })
      .mockResolvedValueOnce({ data: rows(200, 30), total: 230 })
    const { fetchTreatments, treatments } = useTreatments()

    await fetchTreatments('p1')

    expect(treatments.value).toHaveLength(230)
    expect(treatments.value[229]).toMatchObject({ id: 't229', status: 'existing' })
    const urls = getMock.mock.calls.map(c => c[0] as string)
    expect(urls).toEqual([1, 2, 3].map(
      page => `/api/v1/odontogram/patients/p1/treatments?page_size=100&page=${page}`
    ))
  })

  it('makes one request when the first page holds everything', async () => {
    getMock.mockResolvedValueOnce({ data: rows(0, 12), total: 12 })
    const { fetchTreatments, treatments } = useTreatments()

    await fetchTreatments('p1', { status: 'planned' })

    expect(treatments.value).toHaveLength(12)
    expect(getMock).toHaveBeenCalledTimes(1)
    expect(getMock.mock.calls[0]![0]).toBe(
      '/api/v1/odontogram/patients/p1/treatments?status=planned&page_size=100&page=1'
    )
  })

  it('ignores a slower response from the previous patient', async () => {
    let finishFirst: ((value: { data: ReturnType<typeof rows>, total: number }) => void) | undefined
    getMock
      .mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve }))
      .mockResolvedValueOnce({ data: rows(20, 1), total: 1 })
    const { fetchTreatments, treatments } = useTreatments()

    const firstPatientRequest = fetchTreatments('p1')
    await Promise.resolve()
    await fetchTreatments('p2')
    finishFirst?.({ data: rows(1, 1), total: 1 })
    await firstPatientRequest

    expect(treatments.value.map(treatment => treatment.id)).toEqual(['t20'])
  })

  it('clears stale treatments and reports a failed refresh', async () => {
    getMock
      .mockResolvedValueOnce({ data: rows(0, 1), total: 1 })
      .mockRejectedValueOnce(new Error('network down'))
    const { fetchTreatments, treatments, error } = useTreatments()
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})

    await fetchTreatments('p1')
    expect(treatments.value).toHaveLength(1)
    await fetchTreatments('p1')

    expect(treatments.value).toEqual([])
    expect(error.value).toBe('Failed to load treatments')
    consoleError.mockRestore()
  })
})
