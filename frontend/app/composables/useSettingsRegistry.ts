/**
 * Settings registry — categories, pages, search index, onboarding rules.
 *
 * The settings screen is split into a small set of stable categories
 * (general, workspace, people, clinical, billing, communications,
 * integrations, modules, account). Modules contribute *pages* (full
 * child routes, mounted at ``/settings/<category>/<path>``) by calling
 * :func:`registerSettingsPage` from a Nuxt plugin — same registration
 * shape the existing slot system uses.
 *
 * State lives in :func:`useState` so SSR + HMR keep registrations
 * stable across reloads and every consumer (across layers) sees the
 * same map.
 */

import type { Component } from 'vue'
import { PERMISSIONS, type PermissionValue } from '~/config/permissions'
import type { ApiResponse, OnboardingState } from '~/types'

export type ApiClient = ReturnType<typeof useApi>

export type SettingsCategoryId
  = | 'general'
    | 'workspace'
    | 'people'
    | 'clinical'
    | 'billing'
    | 'communications'
    | 'integrations'
    | 'modules'
    | 'account'

export interface SettingsCategory {
  id: SettingsCategoryId
  labelKey: string
  descriptionKey: string
  icon: string
  order: number
  /**
   * If set, the category is hidden when the user lacks this permission
   * AND has no visible page inside it. Pages can still gate themselves
   * independently. Account has no gate (always visible).
   */
  permission?: PermissionValue
}

/**
 * A registered settings page. Renders as a card on the category
 * landing and is mounted at ``/settings/<category>/<path>`` via the
 * shared dynamic route.
 *
 * If ``to`` is provided the entry behaves as an external link card
 * instead of a registered page (no component is mounted) — used for
 * pre-existing pages we don't want to move (e.g. ``/settings/modules``).
 */
export interface SettingsPageEntry {
  /** URL slug. Must be unique within its category. */
  path: string
  category: SettingsCategoryId
  labelKey: string
  descriptionKey?: string
  icon: string
  /**
   * Permission gate. A string requires that exact permission; an array
   * acts as ``canAny`` (visible if the user holds at least one). When
   * unset, the page is visible to all authenticated roles.
   * Typed as {@link PermissionValue} so renames fail at typecheck (#557).
   */
  permission?: PermissionValue | PermissionValue[]
  /** Component mounted at ``/settings/<category>/<path>``. */
  component?: () => Promise<Component | { default: Component }>
  /** External link target — overrides ``component`` when set. */
  to?: string
  /** Synonyms surfaced by Cmd-K (lowercase substrings). */
  searchKeywords?: string[]
  /** Lower numbers render first. Ties resolve in registration order. */
  order?: number
  /** Renders an amber dot when truthy at resolve time. */
  attention?: () => boolean
}

export interface VisibleCategory extends SettingsCategory {
  pages: SettingsPageEntry[]
  hasAttention: boolean
}

export type SettingsSupergroupId
  = | 'clinicalSetup'
    | 'clinicalManagement'
    | 'financialConfiguration'
    | 'systemAddons'
    | 'myPreferences'

/**
 * Presentation-only grouping of the settings rail. The flat category set,
 * the routes and the search index are untouched — the supergroup only
 * orders and labels groups of categories in SettingsCategoryNav.
 */
export interface SettingsSupergroup {
  id: SettingsSupergroupId
  labelKey: string
  categories: VisibleCategory[]
}

export interface SearchEntry {
  id: string
  category: SettingsCategoryId
  label: string
  description?: string
  keywords: string[]
  to: string
  icon: string
}

/**
 * A "getting started" rule. Completion is *derived*: ``when()`` returns
 * true while the step is still pending, reading state that ``load()``
 * (optional) fetched into rule-owned ``useState``. Skip / dismiss are the
 * only stored bits (``clinic.settings.onboarding``, server-side).
 */
export interface GettingStartedRule {
  id: string
  labelKey: string
  descriptionKey?: string
  icon?: string
  /** Settings page (or any route) that resolves the step. */
  to: string
  /** True while the step is still pending. Must be sync and cheap. */
  when: () => boolean
  /**
   * Fetch whatever ``when`` needs. Called by the dashboard card on mount /
   * refresh, possibly from an event handler — so it receives the host's
   * ``useApi()`` client instead of creating one (setup-only composable).
   */
  load?: (api: ApiClient) => Promise<void>
  /**
   * Permission gating the rule — same contract as SettingsPageEntry.
   * ``can()`` embeds module-activation, so a rule from a baked-but-
   * uninstalled module neither renders nor fires its ``load`` (#326).
   */
  permission?: PermissionValue | PermissionValue[]
  /** Guided-mode sequence. Lower first; ties resolve in registration order. */
  order?: number
  /** Optional steps are listed apart and don't count towards progress. */
  optional?: boolean
  /** Lazy mini-modal that resolves the step inline (module-owned component). */
  modal?: () => Promise<Component | { default: Component }>
  severity?: 'info' | 'warning' | 'critical'
}

export interface GettingStartedItem extends GettingStartedRule {
  resolved: boolean
  skipped: boolean
}

const DEFAULT_CATEGORIES: readonly SettingsCategory[] = [
  {
    id: 'general',
    labelKey: 'settings.categories.general.label',
    descriptionKey: 'settings.categories.general.description',
    icon: 'i-lucide-building-2',
    order: 10
  },
  {
    id: 'workspace',
    labelKey: 'settings.categories.workspace.label',
    descriptionKey: 'settings.categories.workspace.description',
    icon: 'i-lucide-layout-grid',
    order: 20
  },
  {
    id: 'people',
    labelKey: 'settings.categories.people.label',
    descriptionKey: 'settings.categories.people.description',
    icon: 'i-lucide-users',
    order: 30,
    permission: PERMISSIONS.users.read
  },
  {
    id: 'clinical',
    labelKey: 'settings.categories.clinical.label',
    descriptionKey: 'settings.categories.clinical.description',
    icon: 'i-lucide-stethoscope',
    order: 40
  },
  {
    id: 'billing',
    labelKey: 'settings.categories.billing.label',
    descriptionKey: 'settings.categories.billing.description',
    icon: 'i-lucide-receipt',
    order: 50
  },
  {
    id: 'communications',
    labelKey: 'settings.categories.communications.label',
    descriptionKey: 'settings.categories.communications.description',
    icon: 'i-lucide-mail',
    order: 60
  },
  {
    id: 'integrations',
    labelKey: 'settings.categories.integrations.label',
    descriptionKey: 'settings.categories.integrations.description',
    icon: 'i-lucide-plug',
    order: 70
  },
  {
    id: 'modules',
    labelKey: 'settings.categories.modules.label',
    descriptionKey: 'settings.categories.modules.description',
    icon: 'i-lucide-blocks',
    order: 80,
    permission: PERMISSIONS.admin.clinicRead
  },
  {
    id: 'account',
    labelKey: 'settings.categories.account.label',
    descriptionKey: 'settings.categories.account.description',
    icon: 'i-lucide-user-circle',
    order: 90
  }
]

/** Category → supergroup. Single source of truth for the settings rail. */
export const CATEGORY_SUPERGROUPS: Record<SettingsCategoryId, SettingsSupergroupId> = {
  general: 'clinicalSetup',
  workspace: 'clinicalSetup',
  people: 'clinicalSetup',
  clinical: 'clinicalManagement',
  billing: 'financialConfiguration',
  communications: 'systemAddons',
  integrations: 'systemAddons',
  modules: 'systemAddons',
  account: 'myPreferences'
}

export const SUPERGROUP_ORDER: readonly SettingsSupergroupId[] = [
  'clinicalSetup',
  'clinicalManagement',
  'financialConfiguration',
  'systemAddons',
  'myPreferences'
]

// Module-level (NOT in `useState`) because entries carry async-component
// functions that the SSR payload cannot serialize. The plugin runs on
// both server and client, so both sides build the same registry
// independently — no transfer needed.
const _pages: SettingsPageEntry[] = []
const _rules: GettingStartedRule[] = []
// Reactive trigger so consumers re-render when registrations change
// (HMR, lazy module installs). Bumping `version` invalidates computeds.
function useRegistryVersion() {
  return useState<number>('settings:registry-version', () => 0)
}

function bumpVersion(): void {
  // Only bump on client — on server `useState` is per-request, so calling
  // it inside a plugin-time register is fine; on client the bump triggers
  // re-render after HMR.
  try {
    const v = useRegistryVersion()
    v.value = v.value + 1
  } catch {
    // useState may throw if called outside a Nuxt context (e.g. tests);
    // module-level state still works for non-reactive lookups.
  }
}

export function registerSettingsPage(entry: SettingsPageEntry): void {
  const id = `${entry.category}.${entry.path}`
  const idx = _pages.findIndex(p => `${p.category}.${p.path}` === id)
  if (idx >= 0) _pages.splice(idx, 1, entry)
  else _pages.push(entry)
  bumpVersion()
}

export function unregisterSettingsPage(category: SettingsCategoryId, path: string): void {
  const idx = _pages.findIndex(p => p.category === category && p.path === path)
  if (idx >= 0) _pages.splice(idx, 1)
  bumpVersion()
}

export function registerGettingStartedRule(rule: GettingStartedRule): void {
  const idx = _rules.findIndex(r => r.id === rule.id)
  if (idx >= 0) _rules.splice(idx, 1, rule)
  else _rules.push(rule)
  bumpVersion()
}

export function unregisterGettingStartedRule(id: string): void {
  const idx = _rules.findIndex(r => r.id === id)
  if (idx >= 0) _rules.splice(idx, 1)
  bumpVersion()
}

export function useSettingsRegistry() {
  const { t } = useI18n()
  const { can, canAny } = usePermissions()

  const version = useRegistryVersion()

  function isPageVisible(page: SettingsPageEntry): boolean {
    if (!page.permission) return true
    return Array.isArray(page.permission)
      ? canAny(page.permission)
      : can(page.permission)
  }

  function isRuleVisible(rule: GettingStartedRule): boolean {
    if (!rule.permission) return true
    return Array.isArray(rule.permission)
      ? canAny(rule.permission)
      : can(rule.permission)
  }

  function pagesByCategory(id: SettingsCategoryId): SettingsPageEntry[] {
    // touch `version` so this is reactive to register/unregister calls
    void version.value
    return [..._pages]
      .filter(p => p.category === id && isPageVisible(p))
      .sort((a, b) => (a.order ?? 0) - (b.order ?? 0))
  }

  const categories = computed<VisibleCategory[]>(() => {
    return DEFAULT_CATEGORIES
      .filter(cat => !cat.permission || can(cat.permission))
      .map((cat) => {
        const visiblePages = pagesByCategory(cat.id)
        return {
          ...cat,
          pages: visiblePages,
          hasAttention: visiblePages.some(p => p.attention?.() === true)
        }
      })
      .sort((a, b) => a.order - b.order)
  })

  /** Categories grouped for the settings rail; empty groups are dropped. */
  const supergroups = computed<SettingsSupergroup[]>(() => {
    const visible = categories.value
    return SUPERGROUP_ORDER
      .map(supergroup => ({
        id: supergroup,
        labelKey: `settings.supergroups.${supergroup}.label`,
        categories: visible.filter(cat => CATEGORY_SUPERGROUPS[cat.id] === supergroup)
      }))
      .filter(group => group.categories.length > 0)
  })

  function findPage(categoryId: SettingsCategoryId, path: string): SettingsPageEntry | null {
    void version.value
    const entry = _pages.find(p => p.category === categoryId && p.path === path)
    return entry && isPageVisible(entry) ? entry : null
  }

  function findCategory(id: string): VisibleCategory | null {
    return categories.value.find(c => c.id === id) ?? null
  }

  function firstVisibleCategory(): VisibleCategory | null {
    return categories.value[0] ?? null
  }

  // ---- Search index ----------------------------------------------------

  const searchIndex = computed<SearchEntry[]>(() => {
    const out: SearchEntry[] = []
    for (const cat of categories.value) {
      // Category landing as a search hit.
      out.push({
        id: cat.id,
        category: cat.id,
        label: t(cat.labelKey),
        description: t(cat.descriptionKey),
        keywords: [cat.id, t(cat.labelKey).toLowerCase()],
        to: `/settings/${cat.id}`,
        icon: cat.icon
      })
      for (const page of cat.pages) {
        const label = t(page.labelKey)
        const description = page.descriptionKey ? t(page.descriptionKey) : undefined
        out.push({
          id: `${cat.id}.${page.path}`,
          category: cat.id,
          label,
          description,
          keywords: [
            page.path,
            label.toLowerCase(),
            ...(page.searchKeywords ?? []).map(k => k.toLowerCase())
          ],
          to: page.to ?? `/settings/${cat.id}/${page.path}`,
          icon: page.icon
        })
      }
    }
    return out
  })

  function search(query: string): SearchEntry[] {
    const q = query.trim().toLowerCase()
    if (!q) return searchIndex.value.slice(0, 8)
    return searchIndex.value
      .map((entry) => {
        const labelHit = entry.label.toLowerCase().includes(q)
        const keywordHit = entry.keywords.some(k => k.includes(q))
        const descHit = entry.description?.toLowerCase().includes(q) ?? false
        if (!labelHit && !keywordHit && !descHit) return null
        // Rank: label > keyword > description
        const rank = labelHit ? 0 : keywordHit ? 1 : 2
        return { entry, rank }
      })
      .filter((x): x is { entry: SearchEntry, rank: number } => x !== null)
      .sort((a, b) => a.rank - b.rank)
      .map(x => x.entry)
      .slice(0, 12)
  }

  // ---- Onboarding ------------------------------------------------------
  // State lives on the clinic (``settings.onboarding``) so it is shared by
  // every admin device; ``useClinic`` already carries it.

  const clinic = useClinic()
  const api = useApi()
  const nuxtApp = useNuxtApp()

  const onboardingState = computed<OnboardingState>(
    () => clinic.currentClinic.value?.settings?.onboarding ?? {}
  )

  /** Every rule (visible to this user), ordered, with derived flags. Never filtered — the card decides. */
  const gettingStartedAll = computed<GettingStartedItem[]>(() => {
    void version.value
    const skipped = onboardingState.value.skipped ?? {}
    return [..._rules]
      .filter(rule => isRuleVisible(rule))
      .map((rule, idx) => ({ rule, idx }))
      .sort((a, b) => (a.rule.order ?? 0) - (b.rule.order ?? 0) || a.idx - b.idx)
      .map(({ rule }) => ({
        ...rule,
        // Computeds may re-evaluate outside a component (watcher flush after
        // an async load) — give predicates the Nuxt context so `useState`
        // works. Predicates must not call setup-only composables (`useI18n`).
        resolved: !nuxtApp.runWithContext(() => rule.when()),
        skipped: rule.id in skipped
      }))
  })

  /** Pending, non-skipped rules — what the settings checklist lists. */
  const gettingStarted = computed<GettingStartedItem[]>(() =>
    gettingStartedAll.value.filter(item => !item.resolved && !item.skipped)
  )

  const isOnboardingDismissed = computed(() =>
    !!onboardingState.value.dismissed_at || !!onboardingState.value.completed_at
  )

  async function patchOnboarding(body: {
    dismissed?: boolean
    completed?: boolean
    skip?: string[]
    unskip?: string[]
    reset?: boolean
  }): Promise<void> {
    try {
      const res = await api.patch<ApiResponse<OnboardingState>>(
        '/api/v1/auth/clinic/settings/onboarding', body
      )
      clinic.patchSettings({ onboarding: res.data })
    } catch (e) {
      console.error('Failed to update onboarding state:', e)
    }
  }

  const dismissOnboarding = () => patchOnboarding({ dismissed: true })
  const resetOnboarding = () => patchOnboarding({ reset: true })
  const completeOnboarding = () => patchOnboarding({ completed: true })
  const skipRule = (id: string) => patchOnboarding({ skip: [id] })
  const unskipRule = (id: string) => patchOnboarding({ unskip: [id] })

  /** Run every visible rule's ``load`` (best effort, in parallel) so ``when`` sees fresh data. */
  async function loadGettingStarted(): Promise<void> {
    // Same gate as isPageVisible (#326): rules of baked-but-uninstalled
    // modules used to fire their API calls on every onboarding refresh
    // (guaranteed 403/404 round-trips).
    const visible = _rules.filter(r => isRuleVisible(r))
    // `version` is captured synchronously (Nuxt context) — after the await
    // `useState` would be unavailable and the bump silently lost.
    await Promise.allSettled(visible.map(r => nuxtApp.runWithContext(() => r.load?.(api))))
    version.value = version.value + 1
  }

  return {
    categories,
    supergroups,
    pagesByCategory,
    findPage,
    findCategory,
    firstVisibleCategory,
    isPageVisible,
    searchIndex,
    search,
    gettingStarted,
    gettingStartedAll,
    loadGettingStarted,
    onboardingState,
    isOnboardingDismissed,
    dismissOnboarding,
    resetOnboarding,
    completeOnboarding,
    skipRule,
    unskipRule,
    register: registerSettingsPage,
    unregister: unregisterSettingsPage,
    registerGettingStartedRule,
    unregisterGettingStartedRule
  }
}
