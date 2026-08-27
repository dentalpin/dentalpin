/**
 * Getting-started orchestration on top of the settings registry rules.
 *
 * - progress = required rules resolved (or skipped) / required rules
 * - guided mode = `?onboarding=<ruleId>` on the current route; the sticky
 *   bar (`OnboardingGuideBar`) reads it and `next()` walks the pending
 *   required rules in `order`. Query flag over composable state: survives
 *   reloads and deep links, nothing to sync.
 * - `openModal(id)` shows a rule's inline mini-modal from the dashboard card.
 */

import type { GettingStartedItem } from '~/composables/useSettingsRegistry'

const REFRESH_THROTTLE_MS = 30_000

export function useOnboarding() {
  const registry = useSettingsRegistry()
  const route = useRoute()
  const { can } = usePermissions()

  const lastRefreshAt = useState<number>('onboarding:last-refresh', () => 0)
  const refreshing = useState<boolean>('onboarding:refreshing', () => false)
  // Rules with `load` read as "resolved" until their data arrives — don't
  // trust progress / completion before the first refresh finished.
  const loaded = useState<boolean>('onboarding:loaded', () => false)
  const activeModalId = useState<string | null>('onboarding:modal', () => null)

  const isAdmin = computed(() => can('admin.clinic.write'))

  const steps = computed<GettingStartedItem[]>(() => registry.gettingStartedAll.value)
  const required = computed(() => steps.value.filter(s => !s.optional))
  const optional = computed(() => steps.value.filter(s => s.optional))
  const pendingRequired = computed(() => required.value.filter(s => !s.resolved && !s.skipped))
  const pendingOptional = computed(() => optional.value.filter(s => !s.resolved && !s.skipped))

  const progress = computed(() => ({
    done: required.value.filter(s => s.resolved || s.skipped).length,
    total: required.value.length
  }))
  const isComplete = computed(() =>
    loaded.value && required.value.length > 0 && pendingRequired.value.length === 0
  )

  async function refresh(force = false): Promise<void> {
    if (refreshing.value) return
    if (!force && Date.now() - lastRefreshAt.value < REFRESH_THROTTLE_MS) return
    refreshing.value = true
    try {
      await registry.loadGettingStarted()
      lastRefreshAt.value = Date.now()
      loaded.value = true
    } finally {
      refreshing.value = false
    }
  }

  // ---- Guided mode ---------------------------------------------------
  const currentStepId = computed(() => {
    const raw = route.query.onboarding
    return typeof raw === 'string' && raw ? raw : null
  })
  const currentStep = computed(() =>
    currentStepId.value ? steps.value.find(s => s.id === currentStepId.value) ?? null : null
  )
  const currentIndex = computed(() =>
    currentStep.value ? required.value.findIndex(s => s.id === currentStep.value!.id) : -1
  )
  const isGuided = computed(() => currentStep.value !== null && isAdmin.value)

  // The bar counts the walk, not the whole checklist: with 4 of 6 steps
  // already done, entering guided mode reads "Step 1 of 2". `start()`
  // freezes the pending list so steps resolved along the way keep their
  // position ("Step 2 of 2", not "Step 1 of 1"). Deep links that bypass
  // start() fall back to the live pending list plus the current step.
  const guidedPlan = useState<string[]>('onboarding:guided-plan', () => [])
  const guidedProgress = computed(() => {
    const id = currentStepId.value
    if (!id) return { current: 0, total: 0 }
    const plan = guidedPlan.value.includes(id)
      ? guidedPlan.value
      : required.value
          .filter(s => (!s.resolved && !s.skipped) || s.id === id)
          .map(s => s.id)
    return { current: plan.indexOf(id) + 1, total: plan.length }
  })

  function stepRoute(step: GettingStartedItem): string {
    const sep = step.to.includes('?') ? '&' : '?'
    return `${step.to}${sep}onboarding=${encodeURIComponent(step.id)}`
  }

  /** Next pending required step after `fromId` (or the first pending one). */
  function nextPending(fromId: string | null): GettingStartedItem | null {
    const list = required.value
    const start = fromId ? list.findIndex(s => s.id === fromId) + 1 : 0
    return list.slice(start).find(s => !s.resolved && !s.skipped)
      ?? list.slice(0, start).find(s => !s.resolved && !s.skipped)
      ?? null
  }

  async function start(): Promise<void> {
    const first = nextPending(null)
    if (!first) return
    guidedPlan.value = pendingRequired.value.map(s => s.id)
    await navigateTo(stepRoute(first))
  }

  async function next(): Promise<boolean> {
    await refresh(true)
    const step = nextPending(currentStepId.value)
    if (!step) {
      guidedPlan.value = []
      await navigateTo('/')
      return false
    }
    await navigateTo(stepRoute(step))
    return true
  }

  async function exit(): Promise<void> {
    guidedPlan.value = []
    await navigateTo({ path: route.path, query: { ...route.query, onboarding: undefined } })
  }

  function openModal(id: string): void {
    activeModalId.value = id
  }

  function closeModal(): void {
    activeModalId.value = null
  }

  return {
    isAdmin,
    steps,
    required,
    optional,
    pendingRequired,
    pendingOptional,
    progress,
    isComplete,
    loaded,
    refresh,
    refreshing,
    // guided mode
    isGuided,
    currentStep,
    currentStepId,
    currentIndex,
    guidedProgress,
    stepRoute,
    start,
    next,
    exit,
    // modals
    activeModalId,
    openModal,
    closeModal,
    // passthrough
    skip: registry.skipRule,
    unskip: registry.unskipRule,
    dismiss: registry.dismissOnboarding,
    complete: registry.completeOnboarding,
    reset: registry.resetOnboarding,
    isDismissed: registry.isOnboardingDismissed,
    state: registry.onboardingState
  }
}
