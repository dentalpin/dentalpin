<script setup lang="ts">
// "Pendientes" feed (IA redesign Fase 2). Read-only list of open work the
// caller can act on — overdue recalls, budgets awaiting response —
// aggregated server-side via the same tools chat uses. Each row
// deep-links to the owning module; the agent performs no writes here.
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

const { t } = useI18n()
const api = useApi()
const { open } = useCopilot()
const { money } = useCopilotFormat()

const items = ref<PendingItem[]>([])
const isLoading = ref(false)
const loaded = ref(false)

async function load() {
  isLoading.value = true
  try {
    const res = await api.get<ApiResponse<PendingItem[]>>('/api/v1/copilot/pending')
    items.value = res.data
  } catch {
    items.value = []
  } finally {
    isLoading.value = false
    loaded.value = true
  }
}

onMounted(load)
defineExpose({ refresh: load })

const groups = computed(() => [
  { kind: 'recall' as const, items: items.value.filter(i => i.kind === 'recall') },
  { kind: 'budget' as const, items: items.value.filter(i => i.kind === 'budget') }
].filter(g => g.items.length))

function iconFor(kind: string): string {
  return kind === 'recall' ? 'i-lucide-phone-call' : 'i-lucide-file-clock'
}

function subtitleFor(item: PendingItem): string {
  if (item.kind === 'recall') return item.reason || ''
  return [item.number, item.amount != null ? money(item.amount) : null]
    .filter(Boolean)
    .join(' · ')
}

async function go(item: PendingItem) {
  open.value = false
  await navigateTo(item.link)
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
        @click="go(item)"
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
    </div>
  </div>
</template>
