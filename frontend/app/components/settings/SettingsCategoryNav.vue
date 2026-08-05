
<script setup lang="ts">
/**
 * Left-rail navigation for the settings IA. Renders the visible
 * categories from the registry, clustered under 5 super-group headers
 * (see ~/config/settingsSuperGroups.ts — purely a display grouping, the
 * registry itself still only knows about its 9 real categories). Used
 * on lg+ as a sticky sidebar; on smaller viewports the same component
 * fills the screen at /settings (the route-driven mobile pattern — tap
 * a row to navigate).
 */
import type { VisibleCategory } from '~/composables/useSettingsRegistry'
import { SETTINGS_SUPER_GROUPS, SETTINGS_CATEGORY_SUPER_GROUP } from '~/config/settingsSuperGroups'

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

interface RenderSuperGroup {
  id: string
  labelKey: string
  order: number
  categories: VisibleCategory[]
}

// Categories with no super-group mapping render last, ungrouped — same
// graceful-degradation rule navGroups.ts uses for the sidebar.
const superGroups = computed<RenderSuperGroup[]>(() => {
  const built: RenderSuperGroup[] = SETTINGS_SUPER_GROUPS.map(g => ({ ...g, categories: [] }))
  for (const cat of registry.categories.value) {
    const superGroupId = SETTINGS_CATEGORY_SUPER_GROUP[cat.id]
    const group = built.find(g => g.id === superGroupId)
    if (group) group.categories.push(cat)
  }
  return built.filter(g => g.categories.length > 0)
})

const ungroupedCategories = computed(() =>
  registry.categories.value.filter(cat => !SETTINGS_CATEGORY_SUPER_GROUP[cat.id])
)
</script>

<template>
  <nav
    class="flex flex-col gap-3"
    :class="fullWidth ? '' : 'sticky top-20'"
    :aria-label="t('settings.navLabel')"
  >
    <div v-for="group in superGroups" :key="group.id" class="space-y-0.5">
      <p class="px-3 pt-2 text-caption text-subtle uppercase tracking-wide">
        {{ t(group.labelKey) }}
      </p>
      <NuxtLink
        v-for="cat in group.categories"
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
    </div>

    <NuxtLink
      v-for="cat in ungroupedCategories"
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
