/**
 * Backend-driven module + navigation registry.
 *
 * Fetches ``GET /api/v1/modules/-/active`` once per session and caches
 * the result in :func:`useState`. The sidebar consumes
 * ``navigationItems`` — entries are permission-filtered on the server
 * and re-translated client-side via i18n. ``ensureLoaded`` is
 * idempotent so guards / layouts can call it without coordinating.
 *
 * If the fetch fails the sidebar shows only the host shell entries
 * (dashboard + settings); module-owned items are gated on the backend
 * response.
 */

import type { ActiveModule, ApiResponse, NavigationItem } from '~/types'

// Host shell nav: dashboard + settings belong to the host app, not to
// any module. Always rendered, even when the modules endpoint fails.
const HOST_NAV: NavigationItem[] = [
  {
    label: 'nav.dashboard',
    icon: 'i-lucide-home',
    to: '/',
    order: 0
  },
  {
    label: 'nav.settings',
    icon: 'i-lucide-settings',
    to: '/settings',
    order: 900
  }
]

/** Context-free read of the active-module list (only ``useState``). */
export function useActiveModulesState() {
  return useState<ActiveModule[] | null>('modules:active', () => null)
}

export function useModules() {
  const { t } = useI18n()
  const { can } = usePermissions()
  const auth = useAuth()
  const api = useApi()

  const active = useActiveModulesState()
  const loading = useState<boolean>('modules:active:loading', () => false)
  const error = useState<string | null>('modules:active:error', () => null)
  const lastLoadedAt = useState<number>('modules:active:at', () => 0)

  async function ensureLoaded(force = false): Promise<void> {
    if (!auth.hasSession.value) return
    if (loading.value) return

    const age = Date.now() - lastLoadedAt.value
    const FRESH_MS = 60_000 // 1 min — cheap enough to refetch often
    if (!force && active.value !== null && age < FRESH_MS) return

    loading.value = true
    error.value = null
    try {
      const response = await api.get<ApiResponse<ActiveModule[]>>(
        '/api/v1/modules/-/active'
      )
      active.value = response.data
      lastLoadedAt.value = Date.now()
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to load modules'
      console.warn('useModules: backend fetch failed —', error.value)
      active.value = null
    } finally {
      loading.value = false
    }
  }

  const modules = computed(() => {
    if (!active.value) return []
    return active.value.map(m => ({
      name: m.name,
      label: m.name,
      icon: '',
      navigation: m.navigation
    }))
  })

  const navigationItems = computed<NavigationItem[]>(() => {
    // Hold off filtering until auth has hydrated. Without this, an early
    // evaluation with empty permissions strips every nav entry that
    // declares a permission, leaving the sidebar at just "Inicio".
    if (!auth.user.value) return []

    const moduleNav = active.value
      ? active.value.flatMap(m => m.navigation)
      : []

    return [...HOST_NAV, ...moduleNav]
      .filter(item => !item.permission || can(item.permission))
      .slice()
      .sort((a, b) => (a.order ?? 999) - (b.order ?? 999))
      .map(item => ({ ...item, label: t(item.label) }))
  })

  return {
    modules,
    navigationItems,
    active,
    loading,
    error,
    ensureLoaded
  }
}
