<script setup lang="ts">
/**
 * PendingChargesCard — "What does this patient owe right now?".
 *
 * Rendered at the top of the patient ``Pagos`` tab, visible only when
 * the FIFO-virtual settle leaves entries uncovered (clinic_receivable
 * > 0). Reception opens this when the patient steps out of the box,
 * sees the recently completed sessions waiting to be charged, and
 * hits "Cobrar" — the amount is pre-filled in the standard payment
 * modal.
 *
 * Read-only summary. The actual collect action is delegated upstream
 * via the ``collect`` emit so the host owns the modal lifecycle.
 */
import { useCurrency } from '~~/app/composables/useCurrency'

interface PendingCharge {
  entry_id: string
  treatment_id: string
  session_id: string | null
  description: string | null
  amount: string
  occurred_at: string
}

const props = defineProps<{
  charges: PendingCharge[]
  canCollect: boolean
}>()

const emit = defineEmits<{
  collect: [amount: number]
}>()

const { t, locale } = useI18n()
const { format: formatCurrency } = useCurrency()

const total = computed(() =>
  props.charges.reduce((acc, c) => acc + (Number(c.amount) || 0), 0)
)

const visibleCharges = computed(() => props.charges.slice(0, 5))
const overflow = computed(() => Math.max(0, props.charges.length - visibleCharges.value.length))

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(locale.value, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit'
  })
}
</script>

<template>
  <UCard
    v-if="charges.length > 0"
    class="border border-warning-accent/40"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-alert-circle"
          class="w-5 h-5 text-warning-accent"
        />
        <span class="font-semibold">{{ t('payments.pendingCharges.title') }}</span>
        <UBadge
          color="warning"
          variant="subtle"
          size="sm"
          class="ms-auto"
        >
          {{ t('payments.pendingCharges.count', { n: charges.length }) }}
        </UBadge>
      </div>
    </template>

    <div class="space-y-3">
      <div class="text-2xl font-semibold text-warning-accent tnum">
        {{ formatCurrency(total) }}
      </div>

      <ul class="space-y-1 text-sm">
        <li
          v-for="charge in visibleCharges"
          :key="charge.entry_id"
          class="flex items-center gap-2"
        >
          <UIcon
            name="i-lucide-circle-dot"
            class="w-3 h-3 text-warning-accent shrink-0"
          />
          <span class="flex-1 min-w-0 truncate">
            {{ charge.description || t('payments.pendingCharges.unnamedSession') }}
          </span>
          <span class="text-muted text-xs shrink-0">{{ formatDate(charge.occurred_at) }}</span>
          <span class="font-medium tnum shrink-0">{{ formatCurrency(Number(charge.amount)) }}</span>
        </li>
      </ul>

      <p
        v-if="overflow > 0"
        class="text-xs text-muted"
      >
        {{ t('payments.pendingCharges.more', { n: overflow }) }}
      </p>

      <UButton
        v-if="canCollect"
        block
        size="lg"
        icon="i-lucide-wallet"
        color="primary"
        @click="emit('collect', total)"
      >
        {{ t('payments.pendingCharges.collect', { amount: formatCurrency(total) }) }}
      </UButton>
    </div>
  </UCard>
</template>
