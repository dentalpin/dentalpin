import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'
import CabinetsPage from '~/components/settings/pages/CabinetsPage.vue'

// #1274: creating, editing and deleting a cabinet is `agenda.cabinets.write`
// on the API, and the agenda manifest gives `dentist` all of `agenda.*`.
// The Settings → Cabinets actions must follow that permission, not the
// admin-only `admin.users.write` behind `isAdmin`.

// What `/me` gives each role (agenda manifest).
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['admin.users.write', 'agenda.cabinets.read', 'agenda.cabinets.write'],
  dentist: ['agenda.cabinets.read', 'agenda.cabinets.write'],
  receptionist: ['agenda.cabinets.read']
}
const role = ref('dentist')
mockNuxtImport('usePermissions', () => () => {
  const can = (p: string) => (ROLE_PERMISSIONS[role.value] ?? []).includes(p)
  return { can, isAdmin: computed(() => can('admin.users.write')) }
})
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('useClinic', () => () => ({
  isLoading: ref(false),
  cabinets: ref([
    { id: 'cab-1', name: 'Box 1', color: '#3B82F6', is_active: true },
    { id: 'cab-2', name: 'Box 2', color: '#10B981', is_active: false }
  ]),
  createCabinet: vi.fn(),
  updateCabinet: vi.fn(),
  deleteCabinet: vi.fn()
}))

describe('Settings → Cabinets actions (#1274)', () => {
  afterEach(() => {
    role.value = 'dentist'
  })

  it.each([
    ['dentist', true],
    ['admin', true],
    ['receptionist', false]
  ])('%s sees add, edit and delete: %s', async (r, visible) => {
    role.value = r
    const wrapper = await mountSuspended(CabinetsPage)
    await flushPromises()
    try {
      expect(wrapper.text()).toContain('Box 1')
      expect(wrapper.text().includes('settings.addCabinet')).toBe(visible)
      expect(wrapper.findAll('button[aria-label="settings.editCabinet"]')).toHaveLength(visible ? 2 : 0)
      expect(wrapper.findAll('button[aria-label="settings.deleteCabinet"]')).toHaveLength(visible ? 2 : 0)
    } finally { wrapper.unmount() }
  })
})
