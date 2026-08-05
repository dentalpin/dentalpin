<script setup lang="ts">
import { NAV_GROUPS, NAV_GROUP_MAP, NAV_SUBGROUPS } from '~/config/navGroups'
import type { NavigationItem } from '~/types'

const props = withDefaults(
  defineProps<{
    items: NavigationItem[]
    isActive: (to: string) => boolean
    variant?: 'desktop' | 'mobile'
  }>(),
  { variant: 'desktop' }
)

const emit = defineEmits<{ (e: 'navigate'): void }>()

const { t } = useI18n()

const linkClass = computed(() =>
  props.variant === 'mobile'
    ? 'group flex items-center gap-3 px-3 py-3 rounded-token-md text-ui transition-colors'
    : 'group flex items-center gap-3 px-3 py-2 rounded-token-md text-ui transition-colors'
)
const iconClass = computed(() =>
  props.variant === 'mobile' ? 'w-5 h-5 shrink-0' : 'w-[18px] h-[18px] shrink-0'
)

function itemClass(to: string) {
  return [
    linkClass.value,
    props.isActive(to)
      ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
      : 'text-muted hover:bg-surface hover:text-default'
  ]
}

// Items with no group mapping render first, flat, in their existing order
// (this is where Home / Schedule land — HOST_NAV / agenda are unmapped).
const ungroupedItems = computed(() =>
  props.items.filter(item => !NAV_GROUP_MAP[item.to])
)

interface RenderSubgroup {
  id: string
  labelKey: string
  order: number
  items: NavigationItem[]
}

interface RenderGroup {
  id: string
  labelKey: string
  order: number
  directItems: NavigationItem[]
  subgroups: RenderSubgroup[]
}

const groups = computed<RenderGroup[]>(() => {
  const built: RenderGroup[] = NAV_GROUPS.map(g => ({ ...g, directItems: [], subgroups: [] }))

  for (const item of props.items) {
    const assignment = NAV_GROUP_MAP[item.to]
    if (!assignment) continue
    const group = built.find(g => g.id === assignment.group)
    if (!group) continue

    if (assignment.subgroup) {
      const def = NAV_SUBGROUPS[assignment.subgroup]
      if (!def) continue
      let sub = group.subgroups.find(s => s.id === assignment.subgroup)
      if (!sub) {
        sub = { id: assignment.subgroup, labelKey: def.labelKey, order: def.order, items: [] }
        group.subgroups.push(sub)
      }
      sub.items.push(item)
    } else {
      group.directItems.push(item)
    }
  }

  return built
    .filter(g => g.directItems.length > 0 || g.subgroups.length > 0)
    .map(g => ({ ...g, subgroups: g.subgroups.sort((a, b) => a.order - b.order) }))
})

// Collapse state per group — shared between the desktop sidebar and the
// mobile drawer via useState (both mount this component), persisted to
// localStorage the same way the parent layout persists isSidebarCollapsed.
const collapsedGroups: Record<string, ReturnType<typeof useState<boolean>>> = {}
for (const g of NAV_GROUPS) {
  collapsedGroups[g.id] = useState(`sidebar:group:${g.id}:collapsed`, () => false)
}

onMounted(() => {
  for (const g of NAV_GROUPS) {
    const saved = localStorage.getItem(`sidebar:group:${g.id}:collapsed`)
    if (saved !== null) {
      collapsedGroups[g.id]!.value = saved === 'true'
    }
  }
})

function toggleGroup(id: string) {
  const state = collapsedGroups[id]
  if (!state) return
  state.value = !state.value
  if (import.meta.client) {
    localStorage.setItem(`sidebar:group:${id}:collapsed`, String(state.value))
  }
}

function handleNavigate() {
  emit('navigate')
}
</script>

<template>
  <nav class="flex-1 px-2 py-2 space-y-1 overflow-y-auto">
    <NuxtLink
      v-for="item in ungroupedItems"
      :key="item.to"
      :to="item.to"
      :class="itemClass(item.to)"
      @click="handleNavigate"
    >
      <UIcon :name="item.icon" :class="iconClass" />
      <span class="truncate">{{ item.label }}</span>
    </NuxtLink>

    <div v-for="group in groups" :key="group.id" class="pt-2">
      <button
        type="button"
        class="w-full flex items-center justify-between px-3 py-1.5 text-caption text-subtle uppercase tracking-wide"
        @click="toggleGroup(group.id)"
      >
        <span class="truncate">{{ t(group.labelKey) }}</span>
        <UIcon
          :name="collapsedGroups[group.id]?.value ? 'i-lucide-chevron-right' : 'i-lucide-chevron-down'"
          class="w-3.5 h-3.5 shrink-0"
        />
      </button>

      <div v-show="!collapsedGroups[group.id]?.value" class="space-y-1">
        <NuxtLink
          v-for="item in group.directItems"
          :key="item.to"
          :to="item.to"
          :class="itemClass(item.to)"
          @click="handleNavigate"
        >
          <UIcon :name="item.icon" :class="iconClass" />
          <span class="truncate">{{ item.label }}</span>
        </NuxtLink>

        <div v-for="sub in group.subgroups" :key="sub.id">
          <p class="px-3 pt-1 text-caption text-subtle truncate">
            {{ t(sub.labelKey) }}
          </p>
          <NuxtLink
            v-for="item in sub.items"
            :key="item.to"
            :to="item.to"
            :class="itemClass(item.to)"
            class="pl-6"
            @click="handleNavigate"
          >
            <UIcon :name="item.icon" :class="iconClass" />
            <span class="truncate">{{ item.label }}</span>
          </NuxtLink>
        </div>
      </div>
    </div>
  </nav>
</template>
