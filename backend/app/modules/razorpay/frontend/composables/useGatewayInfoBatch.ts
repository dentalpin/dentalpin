import type { GatewayInfo } from './useRazorpay'

/**
 * Batches per-row `gateway-info` lookups from the payments list into
 * one HTTP call (#439/#445 review follow-up), instead of each
 * `RazorpayPaymentBadge` instance fetching for itself on mount. Module
 * state — not per-component — so every badge on the same page shares
 * one queue and one cache, the classic "dataloader" pattern.
 */

const cache = new Map<string, GatewayInfo>()
const pending = new Map<string, Array<{ resolve: (v: GatewayInfo) => void, reject: (e: unknown) => void }>>()
let flushTimer: ReturnType<typeof setTimeout> | null = null
// Captured from useRazorpay() while called from a component's setup()
// (see useGatewayInfoBatch below) — the flush timer fires outside any
// component's call stack, where useApi()'s own composable calls
// (useI18n, useToast, ...) would no longer have a Vue instance to
// attach to. The *function* useRazorpay() returns has no such
// requirement once obtained, so it's safe to reuse from the timer.
let fetchBatch: ((ids: string[]) => Promise<Record<string, GatewayInfo>>) | null = null

// ModuleSlot renders each row's badge via `defineAsyncComponent`, so on
// a first (uncached) page load sibling rows can mount a few ticks apart
// — long enough that a microtask-only queue could flush before later
// rows have joined it. A short timeout is the standard dataloader
// trade-off: wide enough to catch a full page of rows in one batch,
// short enough nobody notices the wait.
const FLUSH_DELAY_MS = 20

// Mirrors GatewayInfoBatchRequest.payment_ids' max_length on the
// backend (payment_gateways/schemas.py) — a page size bump past 100
// must chunk into multiple calls instead of every visible row failing
// the request with a 422.
const MAX_BATCH_SIZE = 100

function scheduleFlush(): void {
  if (flushTimer) return
  flushTimer = setTimeout(() => {
    flushTimer = null
    void flush()
  }, FLUSH_DELAY_MS)
}

function resolveChunk(chunk: string[], results: Record<string, GatewayInfo>): void {
  for (const id of chunk) {
    const info: GatewayInfo = results[id] ?? { request: null, refund_requests: [] }
    cache.set(id, info)
    pending.get(id)?.forEach(({ resolve }) => resolve(info))
    pending.delete(id)
  }
}

function rejectChunk(chunk: string[], error: unknown): void {
  for (const id of chunk) {
    pending.get(id)?.forEach(({ reject }) => reject(error))
    pending.delete(id)
  }
}

async function flush(): Promise<void> {
  const ids = [...pending.keys()]
  if (!ids.length || !fetchBatch) return
  const fetcher = fetchBatch
  const chunks: string[][] = []
  for (let i = 0; i < ids.length; i += MAX_BATCH_SIZE) {
    chunks.push(ids.slice(i, i + MAX_BATCH_SIZE))
  }
  // Each chunk resolves/rejects only its own ids, same as a single
  // un-chunked call would have — one chunk failing never blocks or
  // drops the others.
  await Promise.all(chunks.map(async (chunk) => {
    try {
      const results = await fetcher(chunk)
      resolveChunk(chunk, results)
    } catch (e) {
      rejectChunk(chunk, e)
    }
  }))
}

export function useGatewayInfoBatch() {
  // The cache/pending queue below are module-scoped by design (the
  // dataloader pattern this composable implements needs one shared
  // queue per page) — but that only holds for the browser. On the
  // server a module singleton is shared across every concurrent SSR
  // request in the same Node process, so writing to it here would leak
  // one request's fetcher/cache into another's response. The only
  // current caller (`RazorpayPaymentBadge`) already fetches from
  // `onMounted` (client-only), so this is defense-in-depth, not a fix
  // for an observed leak.
  if (import.meta.client) {
    // Refreshed on every call (cheap — useApi() itself holds no state),
    // so the timer always uses a fetcher tied to the most recently
    // mounted badge's own composable context.
    fetchBatch = useRazorpay().getGatewayInfoBatch
  }

  function requestGatewayInfo(paymentId: string): Promise<GatewayInfo> {
    if (!import.meta.client) {
      return Promise.resolve({ request: null, refund_requests: [] })
    }
    const cached = cache.get(paymentId)
    if (cached) return Promise.resolve(cached)
    return new Promise<GatewayInfo>((resolve, reject) => {
      const waiters = pending.get(paymentId)
      if (waiters) {
        waiters.push({ resolve, reject })
      } else {
        pending.set(paymentId, [{ resolve, reject }])
      }
      scheduleFlush()
    })
  }

  // A row updates the cache after e.g. issuing a refund through the
  // transaction detail modal, so a later remount of the same badge (or
  // another instance watching the same payment) doesn't show stale info.
  function updateCache(paymentId: string, info: GatewayInfo): void {
    if (!import.meta.client) return
    cache.set(paymentId, info)
  }

  return { requestGatewayInfo, updateCache }
}
