import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'

interface Filters {
  q: string
  status: string[]
}

const defaults: Filters = { q: '', status: ['active'] }

// Filter changes reach the URL through a debounce timer and then an async
// router navigation, so poll for the outcome rather than sleep a fixed time.
const WAIT = { timeout: 3000, interval: 20 }

// Every test in this file shares one Nuxt app and therefore one router.
// A component left mounted by an earlier test keeps its own useListQuery
// alive, watching and pushing the same URL — two instances then overwrite
// each other's query and whichever debounce lands last wins. That, not the
// wait, is what made this file flaky on CI. Unmount after each test and
// start each one from an empty query.
let mounted: { unmount: () => void } | null = null

beforeEach(async () => {
  await useRouter().replace({ query: {} })
})

afterEach(() => {
  mounted?.unmount()
  mounted = null
})

async function runInSetup<T>(fn: () => T): Promise<T> {
  let captured!: T
  mounted = await mountSuspended(defineComponent({
    setup() {
      captured = fn()
      return () => h('div')
    }
  }))
  return captured
}

function makeListQuery() {
  return useListQuery<Filters, { id: string }>({
    defaults,
    pageSize: 20,
    sortable: [],
    defaultSort: '',
    searchKey: 'q',
    fetcher: async () => ({ data: [], total: 0 })
  })
}

describe('useListQuery array filters with a non-empty default', () => {
  it('keeps an explicitly cleared array cleared (#473)', async () => {
    const { filters, setFilter } = await runInSetup(makeListQuery)
    const route = useRoute()

    // The user picks Archived: the URL records it.
    setFilter('status', ['archived'])
    await vi.waitFor(() => expect(route.query.status).toBe('archived'), WAIT)
    expect(filters.value.status).toEqual(['archived'])

    // ...then clears the filter. An empty selection must survive the
    // round trip through the URL; before the fix the key was dropped
    // entirely, so this wait timed out and re-parsing brought the
    // default back.
    setFilter('status', [])
    await vi.waitFor(() => expect(route.query.status).toBe(''), WAIT)
    // Let the route watcher re-parse the new URL before checking state.
    await nextTick()
    await nextTick()
    expect(filters.value.status).toEqual([])
  })

  it('still omits a filter whose default is already empty', async () => {
    const { filters, setFilter } = await runInSetup(makeListQuery)
    const route = useRoute()

    setFilter('q', 'ana')
    await vi.waitFor(() => expect(route.query.q).toBe('ana'), WAIT)

    // Back to the default: nothing to record, so the key leaves the URL
    // rather than becoming `?q=` noise.
    setFilter('q', '')
    await vi.waitFor(() => expect(route.query.q).toBeUndefined(), WAIT)
    expect(filters.value.q).toBe('')
  })
})
