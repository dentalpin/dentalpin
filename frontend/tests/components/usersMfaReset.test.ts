import { mount } from '@vue/test-utils'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'
import { expect, it, vi } from 'vitest'
import { ref } from 'vue'
import UsersPage from '~/components/settings/pages/UsersPage.vue'

mockNuxtImport('useAuth', () => () => ({ user: ref({ id: 'current-admin' }) }))
mockNuxtImport('usePermissions', () => () => ({ isAdmin: ref(true) }))
mockNuxtImport('useMfa', () => () => ({ request: vi.fn(), message: vi.fn() }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))
mockNuxtImport('useUsers', () => () => ({
  users: ref([
    { id: 'active-factor', first_name: 'With', last_name: 'Factor', role: 'dentist', is_active: true, mfa_enabled: true },
    { id: 'no-factor', first_name: 'Without', last_name: 'Factor', role: 'dentist', is_active: true, mfa_enabled: false },
    { id: 'current-admin', first_name: 'Current', last_name: 'Admin', role: 'admin', is_active: true, mfa_enabled: true }
  ]),
  isLoading: ref(false),
  availableRoles: [],
  fetchUsers: vi.fn()
}))

it('offers an MFA reset only for another staff member with an enrolled factor', () => {
  const page = mount(UsersPage, {
    global: {
      stubs: {
        UButton: { template: '<button><slot /></button>' },
        UModal: true,
        UserCreateModal: true
      }
    }
  })
  const actions = page.findAll('button[aria-label="mfa.reset"]')
  expect(actions).toHaveLength(1)
  expect(actions[0]!.element.parentElement?.parentElement?.textContent).toContain('With Factor')
  page.unmount()
})
