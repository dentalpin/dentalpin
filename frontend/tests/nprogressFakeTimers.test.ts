import NProgress from 'nprogress'
import { describe, expect, it, vi } from 'vitest'

// Captured before any test fakes timers.
const realSetTimeout = globalThis.setTimeout

describe('tests/setup.ts NProgress guard', () => {
  it('a bar whose finishing timer was faked does not fail the file', async () => {
    // A navigation finishes (router.afterEach -> NProgress.done) while the
    // test has timers faked. NProgress schedules each step from the
    // previous one's callback, so the later steps land on the fake clock,
    // and vi.useRealTimers() discards them: the bar is left in the DOM.
    NProgress.start()
    NProgress.done()
    vi.useFakeTimers()
    await new Promise(resolve => realSetTimeout(resolve, 600))
    vi.useRealTimers()

    expect(document.getElementById('nprogress')).not.toBeNull()
    expect(NProgress.isStarted()).toBe(false)
  })
})
