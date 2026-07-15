<script setup lang="ts">
const { t } = useI18n()
const auth = useAuth()
const clinic = useClinic()
const { navigationItems, ensureLoaded } = useModules()
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
  () => auth.accessToken.value,
  (token) => {
    if (token) ensureLoaded(true)
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
  <div class="min-h-screen flex bg-canvas">
    <!-- Desktop/tablet sidebar (hidden on mobile) -->
    <aside
      class="hidden md:flex fixed inset-y-0 left-0 z-50 flex-col bg-surface-muted transition-[width] duration-150 ease-out"
      :class="isSidebarCollapsed ? 'w-16' : 'w-60'"
    >
      <!-- Logo -->
      <div class="flex items-center h-14 px-4">
        <NuxtLink
          to="/"
          class="flex items-center gap-2 overflow-hidden"
          aria-label="DentalPin"
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
            DentalPin
          </span>
        </NuxtLink>
      </div>

      <!-- Navigation -->
      <nav class="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
        <NuxtLink
          v-for="item in mainNavItems"
          :key="item.to"
          :to="item.to"
          class="group flex items-center gap-3 px-3 py-2 rounded-token-md text-ui transition-colors"
          :class="[
            isActive(item.to)
              ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
              : 'text-muted hover:bg-surface hover:text-default'
          ]"
        >
          <UIcon
            :name="item.icon"
            class="w-[18px] h-[18px] shrink-0"
          />
          <span
            v-if="!isSidebarCollapsed"
            class="truncate"
          >
            {{ item.label }}
          </span>
        </NuxtLink>
      </nav>

      <!-- User section -->
      <div class="px-3 py-3 border-t border-subtle">
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
          <NuxtLink
            v-if="settingsItem"
            :to="settingsItem.to"
            :title="settingsItem.label"
            :aria-label="settingsItem.label"
            class="shrink-0 p-1.5 rounded-token-md transition-colors"
            :class="[
              isActive(settingsItem.to)
                ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
                : 'text-muted hover:bg-surface hover:text-default'
            ]"
          >
            <UIcon
              :name="settingsItem.icon"
              class="w-[18px] h-[18px]"
            />
          </NuxtLink>
        </div>
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
              aria-label="DentalPin"
              @click="mobileNavOpen = false"
            >
              <img
                src="/logo-icon.svg"
                alt=""
                width="32"
                height="32"
                class="shrink-0"
              >
              <span class="text-h2 text-default truncate">DentalPin</span>
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
            <NuxtLink
              v-for="item in mainNavItems"
              :key="item.to"
              :to="item.to"
              class="group flex items-center gap-3 px-3 py-3 rounded-token-md text-ui transition-colors"
              :class="[
                isActive(item.to)
                  ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
                  : 'text-muted hover:bg-surface hover:text-default'
              ]"
            >
              <UIcon
                :name="item.icon"
                class="w-5 h-5 shrink-0"
              />
              <span class="truncate">{{ item.label }}</span>
            </NuxtLink>
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
              <NuxtLink
                v-if="settingsItem"
                :to="settingsItem.to"
                :title="settingsItem.label"
                :aria-label="settingsItem.label"
                class="shrink-0 p-2 rounded-token-md transition-colors"
                :class="[
                  isActive(settingsItem.to)
                    ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
                    : 'text-muted hover:bg-surface hover:text-default'
                ]"
              >
                <UIcon
                  :name="settingsItem.icon"
                  class="w-5 h-5"
                />
              </NuxtLink>
            </div>
          </div>
        </div>
      </template>
    </USlideover>

    <!-- Main column -->
    <div
      class="flex-1 flex flex-col min-w-0 transition-[margin] duration-150 ease-out"
      :class="isSidebarCollapsed ? 'md:ml-16' : 'md:ml-60'"
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
          <div class="ml-3 sm:ml-4 flex items-center gap-2 min-w-0">
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
        <div class="flex items-center gap-1">
          <HelpButton />
          <DensityToggle />
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
        <ModuleSlot
          name="app.banners"
          :ctx="{}"
        />
        <slot />
      </main>

      <!--
        Global overlay slot for agent surfaces (the copilot drawer, and
        future voice). Registered components teleport to <body>; nothing
        renders inline here. The layout knows nothing about them.
      -->
      <ModuleSlot
        name="app.overlays"
        :ctx="{}"
      />
    </div>
  </div>
</template>
