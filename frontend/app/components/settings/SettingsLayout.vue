<script setup lang="ts">
/**
 * Top-level layout for /settings routes. Two-pane on lg+, stacked on
 * smaller viewports. The header hosts the page title + Cmd-K search.
 *
 * Children render the right pane on desktop and the only pane on mobile.
 */
import type { SettingsCategoryId } from '~/composables/useSettingsRegistry'

interface Props {
  /** Active category — drives nav highlight + back-button visibility. */
  activeId?: SettingsCategoryId | null
  /** When true, hides the left rail entirely (used on mobile category landing). */
  hideRail?: boolean
  /** Optional back link label. Shown on mobile in pages, not on category landings. */
  backLabel?: string
  /** Optional back link target. */
  backTo?: string
  /** Page title shown in the header. Falls back to ``settings.title``. */
  title?: string
  /** Optional subtitle below the title. */
  subtitle?: string
}

const props = withDefaults(defineProps<Props>(), {
  activeId: null,
  hideRail: false
})

const { t } = useI18n()
const headerTitle = computed(() => props.title ?? t('settings.title'))
</script>

<template>
  <div class="space-y-6">
    <header class="flex items-start justify-between gap-3 flex-wrap">
      <div class="min-w-0 flex-1">
        <NuxtLink
          v-if="backTo"
          :to="backTo"
          class="inline-flex items-center gap-1 text-caption text-muted hover:text-default lg:hidden"
        >
          <UIcon
            name="i-lucide-arrow-left"
            class="w-4 h-4"
          />
          {{ backLabel ?? t('settings.title') }}
        </NuxtLink>
        <h1 class="text-display text-default text-pretty">
          {{ headerTitle }}
        </h1>
        <p
          v-if="subtitle"
          class="mt-1 text-body text-muted text-pretty"
        >
          {{ subtitle }}
        </p>
      </div>

      <div class="shrink-0 w-full sm:w-auto">
        <SettingsSearch />
      </div>
    </header>

    <div class="flex gap-6">
      <!-- Desktop rail. Gated by CSS, not by the media-query ref: useMediaQuery
           is false during SSR, so a v-if here rendered a comment on the server
           and an <aside> on the client (hydration mismatch on every settings page). -->
      <aside
        v-if="!hideRail"
        class="hidden lg:block w-60 shrink-0"
      >
        <SettingsCategoryNav :active-id="activeId" />
      </aside>

      <main class="min-w-0 flex-1">
        <slot />
      </main>
    </div>
  </div>
</template>
