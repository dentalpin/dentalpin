import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
// Module-layer composables are reachable in tests through the
// #module-layers alias (resolved in vitest.config.ts to ../backend/app/modules).
import { usePeriodontogramSession } from '#module-layers/periodontogram/frontend/composables/usePeriodontogramSession'

/**
 * Failed autosave patches must never drop typed measurements (#101):
 * both the debounced flush and the close-time `flushPending` re-queue a
 * failed payload so a retry can persist it.
 */

const SNAPSHOT_ID = 'snap-1'

const { patchMock } = vi.hoisted(() => ({ patchMock: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ patch: patchMock }))

describe('usePeriodontogramSession — pending buffer survives failures', () => {
  beforeEach(() => {
    patchMock.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('flushPending returns true and clears dirty when every patch persists', async () => {
    vi.useFakeTimers()
    patchMock.mockResolvedValue({ data: {} })
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT_ID, 16, 'MB', { probing_depth_mm: 5 })
    expect(session.dirty.value).toBe(true)

    const flushed = await session.flushPending(SNAPSHOT_ID)

    expect(flushed).toBe(true)
    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(patchMock).toHaveBeenCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT_ID}/teeth/16/sites/MB`,
      { probing_depth_mm: 5 }
    )
    expect(session.dirty.value).toBe(false)
  })

  it('flushPending keeps the failed payload so a retry can flush it', async () => {
    vi.useFakeTimers()
    patchMock.mockRejectedValueOnce(new Error('network down'))
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT_ID, 16, 'MB', { probing_depth_mm: 5 })

    const firstAttempt = await session.flushPending(SNAPSHOT_ID)
    expect(firstAttempt).toBe(false)
    expect(session.dirty.value).toBe(true)

    // Retry with the connection back — the buffered payload is re-sent.
    patchMock.mockResolvedValue({ data: {} })
    const secondAttempt = await session.flushPending(SNAPSHOT_ID)

    expect(secondAttempt).toBe(true)
    expect(patchMock).toHaveBeenCalledTimes(2)
    expect(patchMock).toHaveBeenLastCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT_ID}/teeth/16/sites/MB`,
      { probing_depth_mm: 5 }
    )
    expect(session.dirty.value).toBe(false)
  })

  it('edits made after a failed flush merge over the restored payload', async () => {
    vi.useFakeTimers()
    patchMock.mockRejectedValueOnce(new Error('network down'))
    const session = usePeriodontogramSession()

    session.patchSite(SNAPSHOT_ID, 16, 'MB', { probing_depth_mm: 5 })
    await session.flushPending(SNAPSHOT_ID)

    session.patchSite(SNAPSHOT_ID, 16, 'MB', { bleeding_on_probing: true })
    patchMock.mockResolvedValue({ data: {} })
    const flushed = await session.flushPending(SNAPSHOT_ID)

    expect(flushed).toBe(true)
    expect(patchMock).toHaveBeenLastCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT_ID}/teeth/16/sites/MB`,
      { probing_depth_mm: 5, bleeding_on_probing: true }
    )
  })

  it('debounced flush re-queues a failed payload and sets lastError', async () => {
    vi.useFakeTimers()
    patchMock.mockRejectedValueOnce(new Error('network down'))
    const session = usePeriodontogramSession()

    session.patchTooth(SNAPSHOT_ID, 31, { mobility: 2 })
    await vi.advanceTimersByTimeAsync(700)

    expect(patchMock).toHaveBeenCalledTimes(1)
    expect(session.lastError.value).toBe('network down')
    expect(session.dirty.value).toBe(true)

    // The buffered payload is still there for the close-time flush.
    patchMock.mockResolvedValue({ data: {} })
    const flushed = await session.flushPending(SNAPSHOT_ID)

    expect(flushed).toBe(true)
    expect(patchMock).toHaveBeenLastCalledWith(
      `/api/v1/periodontogram/snapshots/${SNAPSHOT_ID}/teeth/31`,
      { mobility: 2 }
    )
    expect(session.dirty.value).toBe(false)
  })
})
