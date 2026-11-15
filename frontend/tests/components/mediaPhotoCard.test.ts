import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import PhotoCard from '#module-layers/media/frontend/components/media/PhotoCard.vue'

const raw = vi.fn(async () => new Response(new Blob(['x']), { status: 200 }))
mockNuxtImport('useApi', () => () => ({
  get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), raw
}))

function doc(mime: string) {
  return {
    id: '00000000-0000-0000-0000-000000000001',
    title: 'IMG0001',
    mime_type: mime,
    thumb_url: '/api/v1/media/documents/1/thumb',
    full_url: '/api/v1/media/documents/1/download'
  }
}

describe('PhotoCard non-image placeholder (#565)', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => raw.mockClear())
  afterEach(() => wrapper?.unmount())

  it('fetches a thumb for an image', async () => {
    wrapper = await mountSuspended(PhotoCard, { props: { document: doc('image/png') } })
    expect(raw).toHaveBeenCalled()
  })

  it('never fetches or renders <img> for a DICOM', async () => {
    wrapper = await mountSuspended(PhotoCard, { props: { document: doc('application/dicom') } })
    expect(raw).not.toHaveBeenCalled()
    expect(wrapper.find('img').exists()).toBe(false)
  })
})
