<script setup lang="ts">
import type { SchedulingSummary } from '../../composables/useReports'
import type { BillingSummary } from '~~/app/types'

defineProps<{ ctx?: unknown }>()

const { t } = useI18n()
const { fetchSchedulingSummary, fetchBillingSummary } = useReports()

const pending = ref(true)
const current = ref<{ sched: SchedulingSummary | null, bill: BillingSummary | null }>({
  sched: null,
  bill: null
})
const previous = ref<{ sched: SchedulingSummary | null, bill: BillingSummary | null }>({
  sched: null,
  bill: null
})

function isoDate(d: Date): string {
  return d.toISOString().split('T')[0] as string
}

async function load() {
  const now = new Date()
  const end = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const start = new Date(end)
  start.setDate(end.getDate() - 6)
  const prevEnd = new Date(start)
  prevEnd.setDate(start.getDate() - 1)
  const prevStart = new Date(prevEnd)
  prevStart.setDate(prevEnd.getDate() - 6)

  const [cs, cb, ps, pb] = await Promise.all([
    fetchSchedulingSummary(isoDate(start), isoDate(end)),
    fetchBillingSummary(isoDate(start), isoDate(end)),
    fetchSchedulingSummary(isoDate(prevStart), isoDate(prevEnd)),
    fetchBillingSummary(isoDate(prevStart), isoDate(prevEnd))
  ])

  current.value = { sched: cs, bill: cb }
  previous.value = { sched: ps, bill: pb }
  pending.value = false
}

onMounted(load)
onActivated(load)

const { format: formatMoney } = useCurrency()

function delta(cur: number, prev: number): { pct: number | null, dir: 'up' | 'down' | 'flat' } {
  if (!prev) return { pct: null, dir: 'flat' }
  const pct = ((cur - prev) / prev) * 100
  if (Math.abs(pct) < 0.5) return { pct: 0, dir: 'flat' }
  return { pct, dir: pct > 0 ? 'up' : 'down' }
}

const kpis = computed(() => {
  const cs = current.value.sched
  const ps = previous.value.sched
  const cb = current.value.bill
  const pb = previous.value.bill

  return [
    {
      key: 'appointments',
      label: t('dashboard.weekGlance.appointments'),
      value: cs ? String(cs.total_appointments) : '—',
      delta: cs && ps ? delta(cs.total_appointments, ps.total_appointments) : null
    },
    {
      key: 'completed',
      label: t('dashboard.weekGlance.completed'),
      value: cs ? `${cs.completed} (${cs.completion_rate.toFixed(0)}%)` : '—',
      delta: cs && ps ? delta(cs.completed, ps.completed) : null
    },
    {
      key: 'invoiced',
      label: t('dashboard.weekGlance.invoiced'),
      value: cb ? formatMoney(cb.total_invoiced) : '—',
      delta: cb && pb ? delta(cb.total_invoiced, pb.total_invoiced) : null
    }
  ]
})

const allMissing = computed(() =>
  !pending.value && !current.value.sched && !current.value.bill
)
</script>

<template>
  <SectionCard
    icon="i-lucide-trending-up"
    icon-role="primary"
    :title="t('dashboard.weekGlance.title')"
  >
    <template #subtitle>
      {{ t('dashboard.weekGlance.subtitle') }}
    </template>

    <div
      v-if="pending"
      class="grid grid-cols-1 sm:grid-cols-3 gap-4"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-16"
      />
    </div>

    <EmptyState
      v-else-if="allMissing"
      icon="i-lucide-bar-chart-3"
      :title="t('dashboard.weekGlance.empty')"
    />

    <div
      v-else
      class="grid grid-cols-1 sm:grid-cols-3 gap-4"
    >
      <div
        v-for="k in kpis"
        :key="k.key"
      >
        <p class="text-caption text-subtle">
          {{ k.label }}
        </p>
        <p class="text-h1 text-default tnum">
          {{ k.value }}
        </p>
        <p
          v-if="k.delta && k.delta.pct !== null"
          class="flex items-center gap-1 text-caption mt-0.5 tnum"
          :class="{
            'text-success-accent': k.delta.dir === 'up',
            'text-danger-accent': k.delta.dir === 'down',
            'text-subtle': k.delta.dir === 'flat'
          }"
        >
          <UIcon
            v-if="k.delta.dir === 'up'"
            name="i-lucide-arrow-up-right"
            class="w-3 h-3"
          />
          <UIcon
            v-else-if="k.delta.dir === 'down'"
            name="i-lucide-arrow-down-right"
            class="w-3 h-3"
          />
          <UIcon
            v-else
            name="i-lucide-minus"
            class="w-3 h-3"
          />
          {{ k.delta.pct === 0 ? '0%' : `${k.delta.pct > 0 ? '+' : ''}${k.delta.pct.toFixed(0)}%` }}
        </p>
      </div>
    </div>
  </SectionCard>
</template>
