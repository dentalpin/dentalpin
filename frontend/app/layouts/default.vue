<script setup lang="ts">
import { groupNavigationItems } from '~/utils/navigation'

const { t } = useI18n()
const auth = useAuth()
const clinic = useClinic()
const { navigationItems, ensureLoaded } = useModules()
const api = useApi()
const { init: initDensity } = useDensity()
const { isTablet } = useBreakpoint()
const route = useRoute()

// Pull the backend-driven nav on mount + on every route change, so
// sidebar reflects module installs/upgrades without a full reload.
// ensureLoaded enforces a 60s freshness window internally.
// Await on server so modules:active lands in the SSR payload — otherwise
// the client hydrates with active=null, then flips branches once the
// fetch resolves, briefly filtering the sidebar down to just Inicio.
if (import.meta.server) {
  await ensureLoaded()
} else {
  ensureLoaded()
}

watch(
  () => auth.isAuthenticated.value,
  (authed) => {
    if (authed) ensureLoaded(true)
  }
)

watch(
  () => route.path,
  () => {
    ensureLoaded()
    // Close mobile drawer on any navigation
    if (mobileNavOpen.value) mobileNavOpen.value = false
  }
)

// Sidebar state (desktop/tablet)
const isSidebarCollapsed = useState('sidebar:collapsed', () => false)

// Mobile drawer state (ephemeral — does not persist)
const mobileNavOpen = ref(false)

// Persist sidebar + init density on client
onMounted(() => {
  const savedState = localStorage.getItem('sidebar:collapsed')
  if (savedState !== null) {
    isSidebarCollapsed.value = savedState === 'true'
  } else if (isTablet.value) {
    // Tablet default: collapsed sidebar for more canvas space
    isSidebarCollapsed.value = true
  }
  initDensity()
  refreshDraftCounts()
})

function toggleSidebar() {
  isSidebarCollapsed.value = !isSidebarCollapsed.value
  if (import.meta.client) {
    localStorage.setItem('sidebar:collapsed', String(isSidebarCollapsed.value))
  }
}

async function handleLogout() {
  await auth.logout()
}

const settingsItem = computed(() => navigationItems.value.find(i => i.to === '/settings'))
const mainNavItems = computed(() => navigationItems.value.filter(i => i.to !== '/settings'))
const draftCounts = reactive({ budgets: 0, plans: 0 })

async function refreshDraftCounts() {
  const hasBudgets = mainNavItems.value.some(item => item.to === '/budgets')
  const hasPlans = mainNavItems.value.some(item => item.to === '/treatment-plans')
  const requests: Promise<void>[] = []
  if (hasBudgets) {
    requests.push(api.get<{ data: unknown[], total: number }>('/api/v1/budget/budgets?page=1&page_size=1&status=draft', { errorToast: false })
      .then((response) => { draftCounts.budgets = response.total })
      .catch(() => { draftCounts.budgets = 0 }))
  }
  if (hasPlans) {
    requests.push(api.get<{ data: unknown[], total: number }>('/api/v1/treatment_plan/treatment-plans?page=1&page_size=1&status=draft', { errorToast: false })
      .then((response) => { draftCounts.plans = response.total })
      .catch(() => { draftCounts.plans = 0 }))
  }
  await Promise.all(requests)
}

watch(mainNavItems, () => {
  if (import.meta.client) refreshDraftCounts()
})
watch(() => route.path, () => {
  if (import.meta.client) refreshDraftCounts()
})

// Collapsible sidebar sections (issue #232): headers are expandable,
// never links. Collapsed map persists in localStorage like the sidebar
// itself (`sidebar:collapsed`); every section starts expanded. When the
// sidebar itself is collapsed, labels are hidden anyway so items render
// flat as before. Loaded in onMounted: the useState initializer runs on
// the server during SSR and hydrates without re-running, so reading
// localStorage there would forget the state on every reload.
const collapsedSections = useState<Record<string, boolean>>('sidebar:nav:collapsed', () => ({}))
onMounted(() => {
  try {
    const saved = JSON.parse(localStorage.getItem('sidebar:nav:collapsed') || '{}')
    if (saved && typeof saved === 'object') collapsedSections.value = saved
  } catch {
    collapsedSections.value = {}
  }
})
const mainNavGroups = computed(() => groupNavigationItems(mainNavItems.value))
// Flat entries (no section) for the drawer and the expanded sidebar;
// the collapsed icon-only sidebar renders everything flat.
const mainNavFlat = computed(() => mainNavGroups.value.flat)
const sidebarItems = computed(
  () => isSidebarCollapsed.value ? mainNavItems.value : mainNavFlat.value
)
function toggleSection(key: string) {
  collapsedSections.value = { ...collapsedSections.value, [key]: !collapsedSections.value[key] }
  if (import.meta.client) {
    localStorage.setItem('sidebar:nav:collapsed', JSON.stringify(collapsedSections.value))
  }
}
function sectionLabel(key: string): string {
  return t(`nav.sections.${key}`, key)
}

// Check if nav item is active
function isActive(to: string): boolean {
  if (to === '/') {
    return route.path === '/'
  }
  if (route.path === to) {
    return true
  }
  if (route.path.startsWith(to + '/')) {
    const moreSpecificNavItem = navigationItems.value.find(item =>
      item.to !== to
      && item.to.length > to.length
      && route.path.startsWith(item.to)
    )
    return !moreSpecificNavItem
  }
  return false
}
</script>

<template>
  <div class="min-h-[100dvh] flex bg-canvas">
    <!-- Desktop/tablet sidebar (hidden on mobile) -->
    <aside
      class="hidden md:flex fixed inset-y-0 start-0 z-50 flex-col bg-surface-muted transition-[width] duration-150 ease-out"
      :class="isSidebarCollapsed ? 'w-16' : 'w-60'"
    >
      <!-- Logo -->
      <div class="flex items-center h-14 px-4">
        <NuxtLink
          to="/"
          class="flex items-center gap-2 overflow-hidden"
          aria-label="Dentum"
        >
          <img
            src="/logo-icon.svg"
            alt=""
            width="32"
            height="32"
            class="shrink-0"
          >
          <span
            v-if="!isSidebarCollapsed"
            class="text-h2 text-default truncate"
          >
            Dentum
          </span>
        </NuxtLink>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
        <NavRow
          v-for="item in sidebarItems"
          :key="item.to"
          :to="item.to"
          :label="item.label"
          :icon="item.icon"
          :active="isActive(item.to)"
          :hide-label="isSidebarCollapsed"
          :count="item.to === '/budgets' ? draftCounts.budgets : item.to === '/treatment-plans' ? draftCounts.plans : undefined"
        />
        <div
          v-for="group in mainNavGroups.groups"
          v-show="!isSidebarCollapsed"
          :key="group.key"
          class="contents"
        >
          <button
            type="button"
            :aria-expanded="!collapsedSections[group.key]"
            :aria-controls="`nav-section-${group.key}`"
            class="w-full flex items-center gap-2 px-3 py-3 text-caption text-subtle uppercase tracking-wide hover:text-default"
            @click="toggleSection(group.key)"
          >
            <span
              :id="`nav-section-${group.key}-label`"
              class="truncate"
            >{{ sectionLabel(group.key) }}</span>
            <UIcon
              name="i-lucide-chevron-down"
              class="w-4 h-4 shrink-0 transition-transform"
              :class="{ 'rotate-180': !collapsedSections[group.key] }"
            />
          </button>
          <div
            v-show="!collapsedSections[group.key]"
            :id="`nav-section-${group.key}`"
            role="region"
            :aria-labelledby="`nav-section-${group.key}-label`"
            class="space-y-1"
          >
            <NavRow
              v-for="item in group.items"
              :key="item.to"
              :to="item.to"
              :label="item.label"
              :icon="item.icon"
              :active="isActive(item.to)"
              :count="item.to === '/budgets' ? draftCounts.budgets : item.to === '/treatment-plans' ? draftCounts.plans : undefined"
            />
          </div>
        </div>
      </nav>

      <!-- User section -->
      <div
        class="py-3 border-t border-subtle"
        :class="isSidebarCollapsed ? 'px-2' : 'px-3'"
      >
        <div
          v-if="auth.user.value"
          class="flex items-center gap-3"
          :class="isSidebarCollapsed ? 'flex-col' : ''"
        >
          <UAvatar
            :alt="auth.user.value.first_name"
            size="sm"
            class="shrink-0"
          />
          <div
            v-if="!isSidebarCollapsed"
            class="flex-1 min-w-0"
          >
            <p class="text-ui text-default truncate">
              {{ auth.user.value.first_name }} {{ auth.user.value.last_name }}
            </p>
            <p class="text-caption text-subtle truncate">
              {{ auth.user.value.email }}
            </p>
          </div>
        </div>
        <NuxtLink
          v-if="settingsItem"
          :to="settingsItem.to"
          :title="settingsItem.label"
          :aria-label="settingsItem.label"
          class="flex min-h-11 items-center rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary-soft)] font-semibold text-[var(--color-primary-soft-text)] shadow-sm transition-colors hover:border-[var(--color-primary)]/60 hover:brightness-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface-muted)]"
          :class="isSidebarCollapsed ? 'mx-auto mt-3 size-11 justify-center p-0' : 'mt-3 w-full justify-center gap-2 px-3 text-sm'"
        >
          <UIcon
            :name="settingsItem.icon"
            class="size-5 shrink-0"
          />
          <span v-if="!isSidebarCollapsed">{{ settingsItem.label }}</span>
        </NuxtLink>
      </div>
    </aside>

    <!-- Mobile drawer nav -->
    <USlideover
      v-model:open="mobileNavOpen"
      side="left"
      :title="t('nav.menu', 'Menú')"
      :ui="{ content: 'w-72 max-w-[80vw] bg-surface-muted' }"
    >
      <template #content>
        <div class="flex flex-col h-full">
          <!-- Logo -->
          <div class="flex items-center justify-between h-14 px-4">
            <NuxtLink
              to="/"
              class="flex items-center gap-2 overflow-hidden"
              aria-label="Dentum"
              @click="mobileNavOpen = false"
            >
              <img
                src="/logo-icon.svg"
                alt=""
                width="32"
                height="32"
                class="shrink-0"
              >
              <span class="text-h2 text-default truncate">Dentum</span>
            </NuxtLink>
            <UButton
              variant="ghost"
              color="neutral"
              size="sm"
              icon="i-lucide-x"
              :aria-label="t('nav.close', 'Cerrar')"
              @click="mobileNavOpen = false"
            />
          </div>

          <!-- Navigation -->
          <nav class="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
            <NavRow
              v-for="item in mainNavFlat"
              :key="item.to"
              :to="item.to"
              :label="item.label"
              :icon="item.icon"
              :active="isActive(item.to)"
              padded="roomy"
              :count="item.to === '/budgets' ? draftCounts.budgets : item.to === '/treatment-plans' ? draftCounts.plans : undefined"
            />
            <div
              v-for="group in mainNavGroups.groups"
              :key="group.key"
              class="contents"
            >
              <button
                type="button"
                :aria-expanded="!collapsedSections[group.key]"
                :aria-controls="`nav-section-m-${group.key}`"
                class="w-full flex items-center gap-2 px-3 py-3 text-caption text-subtle uppercase tracking-wide"
                @click="toggleSection(group.key)"
              >
                <span
                  :id="`nav-section-m-${group.key}-label`"
                  class="truncate"
                >{{ sectionLabel(group.key) }}</span>
                <UIcon
                  name="i-lucide-chevron-down"
                  class="w-4 h-4 shrink-0 transition-transform"
                  :class="{ 'rotate-180': !collapsedSections[group.key] }"
                />
              </button>
              <div
                v-show="!collapsedSections[group.key]"
                :id="`nav-section-m-${group.key}`"
                role="region"
                :aria-labelledby="`nav-section-m-${group.key}-label`"
                class="space-y-1"
              >
                <NavRow
                  v-for="item in group.items"
                  :key="item.to"
                  :to="item.to"
                  :label="item.label"
                  :icon="item.icon"
                  :active="isActive(item.to)"
                  padded="roomy"
                  :count="item.to === '/budgets' ? draftCounts.budgets : item.to === '/treatment-plans' ? draftCounts.plans : undefined"
                />
              </div>
            </div>
          </nav>

          <!-- User section -->
          <div class="px-3 py-3 border-t border-subtle">
            <div
              v-if="auth.user.value"
              class="flex items-center gap-3"
            >
              <UAvatar
                :alt="auth.user.value.first_name"
                size="sm"
                class="shrink-0"
              />
              <div class="flex-1 min-w-0">
                <p class="text-ui text-default truncate">
                  {{ auth.user.value.first_name }} {{ auth.user.value.last_name }}
                </p>
                <p class="text-caption text-subtle truncate">
                  {{ auth.user.value.email }}
                </p>
              </div>
            </div>
            <NuxtLink
              v-if="settingsItem"
              :to="settingsItem.to"
              :title="settingsItem.label"
              :aria-label="settingsItem.label"
              class="mt-3 flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-[var(--color-primary)]/30 bg-[var(--color-primary-soft)] px-3 text-sm font-semibold text-[var(--color-primary-soft-text)] shadow-sm transition-colors hover:border-[var(--color-primary)]/60 hover:brightness-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--color-surface-muted)]"
            >
              <UIcon
                :name="settingsItem.icon"
                class="size-5 shrink-0"
              />
              <span>{{ settingsItem.label }}</span>
            </NuxtLink>
          </div>
        </div>
      </template>
    </USlideover>

    <!-- Main column -->
    <div
      class="flex-1 flex flex-col min-w-0 transition-[margin] duration-150 ease-out"
      :class="isSidebarCollapsed ? 'md:ms-16' : 'md:ms-60'"
    >
      <DemoBanner />

      <!-- Header -->
      <header class="sticky top-0 z-40 flex items-center h-14 px-3 sm:px-4 bg-surface border-b border-subtle">
        <!-- Mobile hamburger -->
        <UButton
          class="md:hidden"
          variant="ghost"
          color="neutral"
          size="sm"
          icon="i-lucide-menu"
          :aria-label="t('nav.openMenu', 'Abrir menú')"
          @click="mobileNavOpen = true"
        />

        <!-- Desktop sidebar toggle -->
        <UButton
          class="hidden md:inline-flex"
          variant="ghost"
          color="neutral"
          size="sm"
          :icon="isSidebarCollapsed ? 'i-lucide-panel-left-open' : 'i-lucide-panel-left-close'"
          :aria-label="t('nav.toggleSidebar', 'Alternar barra lateral')"
          @click="toggleSidebar"
        />

        <!-- Clinic name — client-only to avoid SSR/CSR hydration text mismatch
             ("Clínica" placeholder vs loaded clinic name). -->
        <ClientOnly>
          <div class="ms-2 sm:ms-4 flex max-w-[32vw] items-center gap-2 min-w-0 sm:max-w-[40vw]">
            <UIcon
              name="i-lucide-building-2"
              class="w-4 h-4 text-subtle shrink-0"
            />
            <span class="text-ui text-muted truncate">
              {{ clinic.clinicName.value || t('nav.defaultClinicName') }}
            </span>
          </div>
        </ClientOnly>

        <div class="flex-1" />

        <!-- Right actions -->
        <div class="flex shrink-0 items-center gap-0.5 sm:gap-1">
          <HelpButton />
          <DensityToggle />
          <ThemePicker />
          <UColorModeButton />
          <UButton
            variant="ghost"
            color="neutral"
            size="sm"
            icon="i-lucide-log-out"
            :aria-label="t('auth.logout')"
            @click="handleLogout"
          >
            <span class="hidden sm:inline">{{ t('auth.logout') }}</span>
          </UButton>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 p-3 sm:p-4 md:p-6 min-w-0 overflow-x-hidden">
        <!--
          Global banner slot for compliance modules (Verifactu rejected
          alerts, certificate expiry warnings, etc.). Modules register
          their banners via `useModuleSlots`; the layout knows nothing
          about them.
        -->
        <OnboardingGuideBar />
        <!--
          ClientOnly is load-bearing: slot registrations happen in
          `plugins/slots.client.ts` files, so during SSR this slot is
          empty while the client renders one wrapper per registered
          banner — a layout-level hydration mismatch that blows away
          the page content in <main> (surfaced by india_gst, #210).
          Banners self-reveal after an onMounted fetch anyway, so
          client-only rendering loses nothing.
        -->
        <ClientOnly>
          <ModuleSlot
            name="app.banners"
            :ctx="{}"
          />
        </ClientOnly>
        <slot />
      </main>

      <!--
        Global overlay slot for agent surfaces (the copilot drawer, and
        future voice). Registered components teleport to <body>; nothing
        renders inline here. The layout knows nothing about them.
        ClientOnly for the same reason as app.banners above: overlay
        registrations happen in `plugins/*.client.ts`, so the slot is
        empty during SSR while the client renders the registered
        components — a per-page hydration mismatch otherwise (#258).
      -->
      <ClientOnly>
        <ModuleSlot
          name="app.overlays"
          :ctx="{}"
        />
      </ClientOnly>
    </div>
  </div>
</template>
