/**
 * Registers the host-owned settings pages with the registry. Modules
 * register their own pages via their own client plugins (same pattern
 * as the existing slot system).
 */
import type { ActiveModule, ApiResponse } from '~/types'
import {
  registerSettingsPage,
  registerGettingStartedRule
} from '~/composables/useSettingsRegistry'
import { PERMISSIONS } from '~/config/permissions'

export default defineNuxtPlugin(() => {
  // ---- General -------------------------------------------------------
  registerSettingsPage({
    path: 'clinic',
    category: 'general',
    labelKey: 'settings.clinicInfo',
    descriptionKey: 'settings.clinicInfoDescription',
    icon: 'i-lucide-building-2',
    permission: PERMISSIONS.admin.clinicRead,
    component: () => import('~/components/settings/pages/ClinicInfoPage.vue'),
    searchKeywords: ['clinica', 'clinic', 'cif', 'nif', 'razon social', 'direccion', 'address', 'tax id'],
    order: 10
  })

  // ---- Workspace -----------------------------------------------------
  registerSettingsPage({
    path: 'cabinets',
    category: 'workspace',
    labelKey: 'settings.cabinets',
    descriptionKey: 'settings.cabinetsDescription',
    icon: 'i-lucide-door-open',
    component: () => import('~/components/settings/pages/CabinetsPage.vue'),
    searchKeywords: ['gabinete', 'sala', 'box', 'consulta', 'cabinet', 'room'],
    order: 10
  })

  // ---- People --------------------------------------------------------
  registerSettingsPage({
    path: 'users',
    category: 'people',
    labelKey: 'settings.users',
    descriptionKey: 'settings.usersDescription',
    icon: 'i-lucide-users',
    permission: PERMISSIONS.users.read,
    component: () => import('~/components/settings/pages/UsersPage.vue'),
    searchKeywords: ['usuarios', 'users', 'roles', 'permisos', 'staff', 'equipo', 'team'],
    order: 10
  })

  // ---- Clinical (stub) ----------------------------------------------
  registerSettingsPage({
    path: 'catalog',
    category: 'clinical',
    labelKey: 'catalog.title',
    descriptionKey: 'catalog.description',
    icon: 'i-lucide-list',
    permission: PERMISSIONS.admin.clinicRead,
    to: '/settings/catalog',
    searchKeywords: ['catalogo', 'catalog', 'tratamientos', 'treatments', 'precios', 'prices'],
    order: 10
  })

  // ---- Billing (module-provided pages) ------------------------------
  registerSettingsPage({
    path: 'invoice-series',
    category: 'billing',
    labelKey: 'invoiceSeries.title',
    descriptionKey: 'invoiceSeries.description',
    icon: 'i-lucide-hash',
    permission: PERMISSIONS.admin.clinicRead,
    to: '/settings/invoice-series',
    searchKeywords: ['series', 'numeracion', 'invoice', 'numbering', 'factura'],
    order: 10
  })
  registerSettingsPage({
    path: 'vat-types',
    category: 'billing',
    labelKey: 'vatTypes.title',
    descriptionKey: 'vatTypes.description',
    icon: 'i-lucide-percent',
    permission: PERMISSIONS.admin.clinicRead,
    to: '/settings/vat-types',
    searchKeywords: ['iva', 'vat', 'impuesto', 'tax'],
    order: 20
  })

  // ---- Communications (module-provided pages) ----------------------
  registerSettingsPage({
    path: 'notifications',
    category: 'communications',
    labelKey: 'notifications.title',
    descriptionKey: 'notifications.description',
    icon: 'i-lucide-mail',
    permission: PERMISSIONS.admin.clinicRead,
    to: '/settings/notifications',
    searchKeywords: ['email', 'smtp', 'plantillas', 'templates', 'notificaciones', 'notifications'],
    order: 10
  })

  // ---- Modules (link to existing /settings/modules) -----------------
  registerSettingsPage({
    path: 'manage',
    category: 'modules',
    labelKey: 'settings.modules.title',
    descriptionKey: 'settings.modules.description',
    icon: 'i-lucide-blocks',
    permission: PERMISSIONS.admin.clinicRead,
    to: '/settings/modules',
    searchKeywords: ['modulo', 'module', 'plugin', 'instalar', 'install'],
    order: 10
  })

  // ---- Account -------------------------------------------------------
  registerSettingsPage({
    path: 'profile',
    category: 'account',
    labelKey: 'settings.profile',
    descriptionKey: 'settings.profileDescription',
    icon: 'i-lucide-user',
    component: () => import('~/components/settings/pages/ProfilePage.vue'),
    searchKeywords: ['perfil', 'profile', 'cuenta', 'account'],
    order: 10
  })
  registerSettingsPage({
    path: 'language',
    category: 'account',
    labelKey: 'settings.language',
    descriptionKey: 'settings.languageDescription',
    icon: 'i-lucide-languages',
    component: () => import('~/components/settings/pages/LanguagePage.vue'),
    searchKeywords: ['idioma', 'language', 'locale', 'lang'],
    order: 20
  })

  // ---- Onboarding rules ---------------------------------------------
  // The dashboard card itself is registered by `onboarding.slots.client.ts`
  // (slot entries hold components — client only). Rules read state lazily
  // inside `when` to stay reactive across login transitions; module
  // plugins register their own rules.
  registerGettingStartedRule({
    id: 'clinic-info-incomplete',
    labelKey: 'settings.onboarding.items.clinicInfo.label',
    descriptionKey: 'settings.onboarding.items.clinicInfo.description',
    icon: 'i-lucide-building-2',
    to: '/settings/general/clinic',
    order: 10,
    severity: 'warning',
    when: () => {
      const c = useClinicState().currentClinic.value
      if (!c) return false
      return !c.name || !c.tax_id || !c.address?.street
    }
  })

  registerGettingStartedRule({
    id: 'no-cabinets',
    labelKey: 'settings.onboarding.items.cabinets.label',
    descriptionKey: 'settings.onboarding.items.cabinets.description',
    icon: 'i-lucide-door-open',
    to: '/settings/workspace/cabinets',
    order: 20,
    severity: 'info',
    modal: () => import('~/components/settings/cabinets/CabinetFormModal.vue'),
    when: () => {
      const c = useClinicState().currentClinic.value
      return !!c && (c.cabinets ?? []).length === 0
    }
  })

  // Team: at least one professional who can be booked — another active
  // member, or the admin flagged as professional (solo practice).
  registerGettingStartedRule({
    id: 'team',
    labelKey: 'onboarding.items.team.label',
    descriptionKey: 'onboarding.items.team.description',
    icon: 'i-lucide-users',
    to: '/settings/people/users',
    order: 40,
    severity: 'info',
    modal: () => import('~/components/settings/users/UserCreateModal.vue'),
    load: async (api) => {
      const state = useState<{ loaded: boolean, professionals: number, others: number }>(
        'onboarding:team', () => ({ loaded: false, professionals: 0, others: 0 })
      )
      // Background onboarding probe — never toast from here.
      const res = await api.get<{ data: Array<{ is_active: boolean, is_professional: boolean }> }>(
        '/api/v1/auth/users',
        { errorToast: false }
      )
      const list = res.data.filter(u => u.is_active)
      state.value = {
        loaded: true,
        professionals: list.filter(u => u.is_professional).length,
        others: list.length - 1
      }
    },
    when: () => {
      const state = useState<{ loaded: boolean, professionals: number, others: number }>(
        'onboarding:team', () => ({ loaded: false, professionals: 0, others: 0 })
      )
      if (!state.value.loaded) return false
      return state.value.professionals === 0 && state.value.others === 0
    }
  })

  // Spain: VeriFactu is the legal invoicing record system — suggest it
  // when the module isn't active. Optional (skippable).
  registerGettingStartedRule({
    id: 'verifactu',
    labelKey: 'onboarding.items.verifactu.label',
    descriptionKey: 'onboarding.items.verifactu.description',
    icon: 'i-lucide-shield-check',
    to: '/settings/modules',
    order: 70,
    optional: true,
    severity: 'info',
    load: async (api) => {
      const active = useActiveModulesState()
      if (active.value) return
      // Background onboarding probe — never toast from here.
      const res = await api.get<ApiResponse<ActiveModule[]>>('/api/v1/modules/-/active', { errorToast: false })
      active.value = res.data
    },
    when: () => {
      const c = useClinicState().currentClinic.value
      if (c?.settings?.country !== 'ES') return false
      const active = useActiveModulesState().value
      if (!active) return false
      return !active.some(m => m.name === 'verifactu')
    }
  })
})
