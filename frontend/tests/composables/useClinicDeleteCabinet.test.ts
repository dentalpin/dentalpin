import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { useClinic } from '../../app/composables/useClinic'

/** #1237: a cabinet with appointments answers 409; the toast must say to deactivate it. */
const del = vi.fn()
const add = vi.fn()

mockNuxtImport('useApi', () => () => ({ del, get: vi.fn(), post: vi.fn(), put: vi.fn() }))
mockNuxtImport('useToast', () => () => ({ add }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))
mockNuxtImport('useAuth', () => () => ({ isAuthenticated: ref(false) }))

describe('useClinic().deleteCabinet', () => {
  beforeEach(() => {
    del.mockReset()
    add.mockReset()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  it('tells the user to deactivate a cabinet that has appointments', async () => {
    del.mockRejectedValue({ statusCode: 409 })
    expect(await useClinic().deleteCabinet('cab-1')).toBe(false)
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ description: 'cabinet.toast.deleteHasHistory' }))
  })

  it('keeps the generic message for other failures', async () => {
    del.mockRejectedValue({ statusCode: 500 })
    await useClinic().deleteCabinet('cab-1')
    expect(add).toHaveBeenCalledWith(expect.objectContaining({ description: 'cabinet.toast.deleteFailed' }))
  })
})
