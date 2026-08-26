<script setup lang="ts">
/**
 * PlanItemSessionRow — one row of the session list rendered inside an item.
 *
 * Sessions split a plan item into named billable steps (e.g. crown:
 * "Toma de medidas" 200€ + "Colocación" 600€). Completion is per-row;
 * completing the last pending session finalizes the parent item.
 */
import type { PlanItemSession } from '~~/app/types'

defineProps<{
  session: PlanItemSession
  canComplete?: boolean
}>()

const emit = defineEmits<{
  complete: [sessionId: string]
  cancel: [sessionId: string]
}>()

const { t } = useI18n()
const { format: formatCurrency } = useCurrency()

function amountValue(amount: number | string): number {
  const n = typeof amount === 'string' ? Number(amount) : amount
  return Number.isFinite(n) ? n : 0
}
</script>

<template>
  <div
    class="flex items-center gap-2 px-2 py-1.5 rounded text-sm"
    :class="{
      'bg-surface-muted': session.status !== 'pending',
      'bg-surface border border-default': session.status === 'pending'
    }"
  >
    <span class="text-subtle text-caption tnum w-6 text-center shrink-0">
      {{ session.sequence }}.
    </span>
    <UIcon
      v-if="session.status === 'completed'"
      name="i-lucide-check-circle"
      class="w-4 h-4 text-success-accent shrink-0"
    />
    <UIcon
      v-else-if="session.status === 'cancelled'"
      name="i-lucide-x-circle"
      class="w-4 h-4 text-muted shrink-0"
    />
    <UIcon
      v-else
      name="i-lucide-circle-dashed"
      class="w-4 h-4 text-muted shrink-0"
    />
    <span
      class="flex-1 min-w-0 break-words"
      :class="{ 'line-through text-muted': session.status !== 'pending' }"
    >
      {{ session.label || t('clinical.plans.sessions.untitled', { n: session.sequence }) }}
    </span>
    <span class="font-medium text-sm tnum shrink-0">
      {{ formatCurrency(amountValue(session.amount)) }}
    </span>
    <span
      v-if="session.completed_at"
      class="text-xs text-muted shrink-0"
    >
      {{ new Date(session.completed_at).toLocaleDateString() }}
    </span>
    <UButton
      v-if="canComplete && session.status === 'pending'"
      size="xs"
      variant="ghost"
      color="success"
      icon="i-lucide-check"
      :aria-label="t('clinical.plans.sessions.markDone')"
      :title="t('clinical.plans.sessions.markDone')"
      @click.stop="emit('complete', session.id)"
    />
    <UButton
      v-if="canComplete && session.status === 'pending'"
      size="xs"
      variant="ghost"
      color="error"
      icon="i-lucide-x"
      :aria-label="t('clinical.plans.sessions.cancel')"
      :title="t('clinical.plans.sessions.cancel')"
      @click.stop="emit('cancel', session.id)"
    />
  </div>
</template>
