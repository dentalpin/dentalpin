import { mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick } from 'vue'

interface Filters {
  q: string
  status: string[]
}

const defaults: Filters = { q: '', status: ['active'] }

async function settle(urlReflects: () => void): Promise<void> {
  // The URL push is debounced behind the search key's timer, and the
  // route watcher that re-parses it runs a tick later. Poll for the URL
  // instead of sleeping a fixed time: 400 ms against the 300 ms debounce
  // plus an async router.replace was too tight for slow CI runners.
  await vi.waitFor(urlReflects, { timeout: 5000 })
  await nextTick()
  await nextTick()
}

// Every test in this file shares one Nuxt app, and therefore one router.
// A component left mounted by an earlier test keeps its own useListQuery
// alive, watching and pushing the same URL — two instances then overwrite
// each other's query and whichever debounced push lands last wins. That is
// what made the second case flaky on CI (it turned #460, #464 and #476 red
// on diffs that touch no frontend code); polling instead of sleeping made
// it rarer but could not fix it, because the state never converges.
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

describe('useListQuery array filters with a non-empty default', () => {
  it('keeps an explicitly cleared array cleared (#473)', async () => {
    const { filters, setFilter } = await runInSetup(() =>
      useListQuery<Filters, { id: string }>({
        defaults,
        pageSize: 20,
        sortable: [],
        defaultSort: '',
        searchKey: 'q',
        fetcher: async () => ({ data: [], total: 0 })
      })
    )
    const route = useRoute()

    // The user picks Archived: the URL records it.
    setFilter('status', ['archived'])
    await settle(() => expect(route.query.status).toBe('archived'))
    expect(filters.value.status).toEqual(['archived'])

    // ...then clears the filter. An empty selection must survive the
    // round trip through the URL; before the fix the key was dropped
    // entirely and re-parsing brought the default back.
    setFilter('status', [])
    await settle(() => expect(route.query.status).toBe(''))
    expect(filters.value.status).toEqual([])
  })

  it('still omits a filter whose default is already empty', async () => {
    const { filters, setFilter } = await runInSetup(() =>
      useListQuery<Filters, { id: string }>({
        defaults,
        pageSize: 20,
        sortable: [],
        defaultSort: '',
        searchKey: 'q',
        fetcher: async () => ({ data: [], total: 0 })
      })
    )
    const route = useRoute()

    setFilter('q', 'ana')
    await settle(() => expect(route.query.q).toBe('ana'))

    // Back to the default: nothing to record, so the key leaves the URL
    // rather than becoming `?q=` noise.
    setFilter('q', '')
    await settle(() => expect(route.query.q).toBeUndefined())
    expect(filters.value.q).toBe('')
  })
})
