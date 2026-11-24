<script setup lang="ts">
// "Pendientes" feed (IA redesign Fase 2). Read-only list of open work the
// caller can act on — overdue recalls, budgets awaiting response —
// aggregated server-side via the same tools chat uses. Each row
// deep-links to the owning module; the agent performs no writes here.
// Each kind shows a bounded slice; when its section total is larger the
// group says "showing N of M" and links to the full list (#1137).
import type { ApiResponse } from '~~/app/types'

interface PendingItem {
  kind: 'recall' | 'budget'
  id: string
  patient_id: string | null
  title: string | null
  link: string
  reason: string | null
  priority: string | null
  number: string | null
  amount: number | null
}

interface PendingSection {
  kind: 'recall' | 'budget'
  total: number
  link: string
}

interface PendingResponse {
  items: PendingItem[]
  sections: PendingSection[]
}

const { t } = useI18n()
const api = useApi()
const { open } = useCopilot()
const { money } = useCopilotFormat()

const items = ref<PendingItem[]>([])
const sections = ref<PendingSection[]>([])
const isLoading = ref(false)
const loaded = ref(false)

async function load() {
  isLoading.value = true
  try {
    const res = await api.get<ApiResponse<PendingResponse>>('/api/v1/copilot/pending')
    items.value = res.data.items
    sections.value = res.data.sections
  } catch {
    items.value = []
    sections.value = []
  } finally {
    isLoading.value = false
    loaded.value = true
  }
}

onMounted(load)
defineExpose({ refresh: load })

const groups = computed(() => (['recall', 'budget'] as const)
  .map((kind) => {
    const groupItems = items.value.filter(i => i.kind === kind)
    const section = sections.value.find(s => s.kind === kind)
    const total = Math.max(section?.total ?? 0, groupItems.length)
    return {
      kind,
      items: groupItems,
      total,
      moreLink: section && total > groupItems.length ? section.link : null
    }
  })
  .filter(g => g.items.length))

function iconFor(kind: string): string {
  return kind === 'recall' ? 'i-lucide-phone-call' : 'i-lucide-file-clock'
}

function subtitleFor(item: PendingItem): string {
  if (item.kind === 'recall') return item.reason || ''
  return [item.number, item.amount != null ? money(item.amount) : null]
    .filter(Boolean)
    .join(' · ')
}

async function go(link: string) {
  open.value = false
  await navigateTo(link)
}
</script>

<template>
  <div class="flex flex-col gap-4 p-1">
    <USkeleton
      v-if="isLoading && !loaded"
      class="h-24 w-full"
    />

    <div
      v-else-if="!items.length"
      class="flex flex-col items-center gap-3 px-2 py-10 text-center text-muted"
    >
      <UIcon
        name="i-lucide-check-circle-2"
        class="size-7 text-success"
      />
      <p class="text-sm">
        {{ t('copilot.pending.empty') }}
      </p>
    </div>

    <div
      v-for="g in groups"
      v-else
      :key="g.kind"
      class="flex flex-col gap-2"
    >
      <p class="px-1 text-xs font-medium uppercase tracking-wide text-muted">
        {{ t(`copilot.pending.group.${g.kind}`) }}
      </p>
      <button
        v-for="item in g.items"
        :key="`${item.kind}-${item.id}`"
        type="button"
        class="flex items-center gap-3 rounded-lg border border-default p-3 text-start transition hover:bg-elevated"
        @click="go(item.link)"
      >
        <UIcon
          :name="iconFor(item.kind)"
          class="size-4 shrink-0 text-primary"
        />
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium">
            {{ item.title || t('copilot.pending.unknownPatient') }}
          </p>
          <p
            v-if="subtitleFor(item)"
            class="truncate text-xs text-muted"
          >
            {{ subtitleFor(item) }}
          </p>
        </div>
        <UIcon
          name="i-lucide-chevron-right"
          class="size-4 shrink-0 text-muted"
        />
      </button>
      <UButton
        v-if="g.moreLink"
        :data-testid="`pending-more-${g.kind}`"
        variant="link"
        size="sm"
        class="self-start"
        trailing-icon="i-lucide-arrow-right"
        @click="go(g.moreLink)"
      >
        {{ t('copilot.pending.more', { shown: g.items.length, total: g.total }) }}
      </UButton>
    </div>
  </div>
</template>
