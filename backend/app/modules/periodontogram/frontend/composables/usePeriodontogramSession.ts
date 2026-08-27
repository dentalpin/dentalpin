/**
 * Session-edit composable for a single periodontogram snapshot.
 *
 * Wraps the PATCH / close / discard endpoints with a tiny debouncer
 * so per-cell edits coalesce into one network call per ~600ms.
 * `dirty` and `saving` flags drive the UI's autosave indicator.
 */

import { ref } from 'vue'
import type { PerioSite, PerioSnapshotDetail, PerioTooth, SiteCode } from '../types'

interface ApiResponse<T> {
  data: T
}

type ToothPatch = Partial<
  Pick<
    PerioTooth,
    | 'is_present'
    | 'is_implant'
    | 'mobility'
    | 'prognosis'
    | 'furcation_buccal'
    | 'furcation_lingual'
    | 'keratinized_gingiva_mm'
  >
>

type SitePatch = Partial<
  Pick<
    PerioSite,
    | 'probing_depth_mm'
    | 'gingival_margin_mm'
    | 'bleeding_on_probing'
    | 'plaque'
    | 'suppuration'
  >
>

const DEBOUNCE_MS = 600

export function usePeriodontogramSession() {
  const api = useApi()
  const saving = ref(false)
  const dirty = ref(false)
  const lastError = ref<string | null>(null)
  const pendingTimers = new Map<string, ReturnType<typeof setTimeout>>()
  const pendingPayloads = new Map<string, Record<string, unknown>>()

  /**
   * Re-queue a payload whose PATCH failed so a later flush (next edit on
   * the same key, or the close-time `flushPending`) retries it. Edits made
   * while the request was in flight win over the failed payload.
   */
  function _restorePayload(key: string, payload: Record<string, unknown>) {
    pendingPayloads.set(key, { ...payload, ...(pendingPayloads.get(key) ?? {}) })
    dirty.value = true
  }

  function _flushKey(key: string, exec: (payload: Record<string, unknown>) => Promise<void>) {
    return async () => {
      const payload = pendingPayloads.get(key)
      if (!payload) return
      pendingPayloads.delete(key)
      pendingTimers.delete(key)
      saving.value = true
      try {
        await exec(payload)
        lastError.value = null
        if (pendingPayloads.size === 0) dirty.value = false
      } catch (e) {
        // Keep the measurements in the buffer — dropping them here would
        // silently lose typed input on a transient failure.
        _restorePayload(key, payload)
        lastError.value = e instanceof Error ? e.message : 'save_failed'
      } finally {
        saving.value = false
      }
    }
  }

  function _schedule(
    key: string,
    patch: Record<string, unknown>,
    exec: (payload: Record<string, unknown>) => Promise<void>
  ) {
    dirty.value = true
    const merged = { ...(pendingPayloads.get(key) ?? {}), ...patch }
    pendingPayloads.set(key, merged)
    const prev = pendingTimers.get(key)
    if (prev) clearTimeout(prev)
    pendingTimers.set(key, setTimeout(_flushKey(key, exec), DEBOUNCE_MS))
  }

  function patchTooth(snapshotId: string, toothNumber: number, patch: ToothPatch) {
    _schedule(`tooth:${toothNumber}`, patch as Record<string, unknown>, async (payload) => {
      await api.patch<ApiResponse<PerioTooth>>(
        `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}`,
        payload
      )
    })
  }

  function patchSite(
    snapshotId: string,
    toothNumber: number,
    siteCode: SiteCode,
    patch: SitePatch
  ) {
    _schedule(
      `site:${toothNumber}:${siteCode}`,
      patch as Record<string, unknown>,
      async (payload) => {
        await api.patch<ApiResponse<PerioSite>>(
          `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}/sites/${siteCode}`,
          payload
        )
      }
    )
  }

  /**
   * Flush every pending patch immediately (e.g. before closing the exam).
   *
   * Returns `true` only when everything was persisted. On failure the
   * failed payloads stay in the buffer (so a retry can flush them) and
   * `dirty` stays true — callers must not proceed with a close/teardown
   * that would orphan the unsaved measurements.
   */
  async function flushPending(snapshotId: string): Promise<boolean> {
    let allFlushed = true
    for (const timer of pendingTimers.values()) {
      clearTimeout(timer)
    }
    pendingTimers.clear()
    // Iterate the payloads (not the timers) — a payload restored after a
    // failed flush no longer has a timer but still must be sent.
    for (const key of Array.from(pendingPayloads.keys())) {
      const payload = pendingPayloads.get(key)
      if (!payload) continue
      pendingPayloads.delete(key)
      saving.value = true
      try {
        if (key.startsWith('tooth:')) {
          const toothNumber = Number(key.slice('tooth:'.length))
          await api.patch(
            `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothNumber}`,
            payload
          )
        } else if (key.startsWith('site:')) {
          const [, toothStr, siteCode] = key.split(':')
          await api.patch(
            `/api/v1/periodontogram/snapshots/${snapshotId}/teeth/${toothStr}/sites/${siteCode}`,
            payload
          )
        }
      } catch {
        // No lastError here — the caller surfaces the failure from the
        // boolean result (avoids a double toast via the lastError watcher).
        _restorePayload(key, payload)
        allFlushed = false
      } finally {
        saving.value = false
      }
    }
    if (allFlushed && pendingPayloads.size === 0) {
      dirty.value = false
    }
    return allFlushed
  }

  async function closeSession(snapshotId: string, notes?: string): Promise<PerioSnapshotDetail> {
    saving.value = true
    try {
      const response = await api.post<ApiResponse<PerioSnapshotDetail>>(
        `/api/v1/periodontogram/snapshots/${snapshotId}/close`,
        { notes: notes ?? null }
      )
      dirty.value = false
      return response.data
    } finally {
      saving.value = false
    }
  }

  async function discardDraft(snapshotId: string): Promise<void> {
    saving.value = true
    try {
      await api.del(`/api/v1/periodontogram/snapshots/${snapshotId}`)
      dirty.value = false
    } finally {
      saving.value = false
    }
  }

  return {
    saving,
    dirty,
    lastError,
    patchTooth,
    patchSite,
    flushPending,
    closeSession,
    discardDraft
  }
}
