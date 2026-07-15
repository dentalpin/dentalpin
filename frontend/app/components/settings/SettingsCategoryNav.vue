<script setup lang="ts">
/**
 * Left-rail navigation for the settings IA. Renders the visible
 * categories from the registry. Used on lg+ as a sticky sidebar; on
 * smaller viewports the same component fills the screen at /settings
 * (the route-driven mobile pattern — tap a row to navigate).
 */
import type { VisibleCategory } from '~/composables/useSettingsRegistry'

interface Props {
  /** Active category id (resolved from the current route). */
  activeId?: string | null
  /** When true, render at full width without sticky / w-60. */
  fullWidth?: boolean
}

withDefaults(defineProps<Props>(), {
  activeId: null,
  fullWidth: false
})

const { t } = useI18n()
const registry = useSettingsRegistry()

function categoryLabel(cat: VisibleCategory): string {
  return t(cat.labelKey)
}

function categoryDescription(cat: VisibleCategory): string {
  return t(cat.descriptionKey)
}

function categoryHref(cat: VisibleCategory): string {
  return `/settings/${cat.id}`
}
</script>

<template>
  <nav
    class="flex flex-col gap-0.5"
    :class="fullWidth ? '' : 'sticky top-20'"
    :aria-label="t('settings.navLabel')"
  >
    <NuxtLink
      v-for="cat in registry.categories.value"
      :key="cat.id"
      :to="categoryHref(cat)"
      class="group flex items-center gap-3 rounded-md px-3 py-2.5 min-h-[44px] transition border-l-2"
      :class="[
        activeId === cat.id
          ? 'bg-(--color-primary-soft) border-(--color-primary) text-default'
          : 'border-transparent hover:bg-(--color-surface-muted) text-default'
      ]"
    >
      <UIcon
        :name="cat.icon"
        class="w-5 h-5 shrink-0"
        :class="activeId === cat.id ? 'text-(--color-primary-accent)' : 'text-muted group-hover:text-default'"
      />
      <div class="min-w-0 flex-1">
        <div class="flex items-center gap-2">
          <span class="text-body font-medium truncate">
            {{ categoryLabel(cat) }}
          </span>
          <span
            v-if="cat.hasAttention"
            class="w-2 h-2 rounded-full bg-(--color-warning-accent) shrink-0"
            :aria-label="t('settings.attentionRequired')"
          />
        </div>
        <p
          v-if="!fullWidth"
          class="hidden lg:block text-caption text-subtle truncate"
        >
          {{ categoryDescription(cat) }}
        </p>
      </div>
      <UIcon
        v-if="fullWidth"
        name="i-lucide-chevron-right"
        class="w-5 h-5 text-subtle shrink-0 lg:hidden"
      />
    </NuxtLink>
  </nav>
</template>
