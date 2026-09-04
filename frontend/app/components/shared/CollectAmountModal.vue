<script setup lang="ts">
/**
 * Reusable "collect amount" modal — amount-first input, visual method
 * picker, date with "Hoy" shortcut, optional reference/notes. Used by
 * BudgetCollectModal (payments module) and InvoiceCollectModal
 * (billing module). The host wraps it with the appropriate API call.
 *
 * The narration slot lets the caller render context-specific copy
 * (e.g. budget split into pending + on-account, or single-target
 * invoice). The modal exposes computed `amount` via the slot.
 */

import type { PaymentMethod } from '~~/app/types'

interface Props {
  open: boolean
  title: string
  subtitle?: string
  pendingAmount: number
  submitLabel?: string
  submitIcon?: string
  submitting?: boolean
  error?: string | null
}

const props = withDefaults(defineProps<Props>(), {
  subtitle: undefined,
  submitIcon: 'i-lucide-wallet',
  submitting: false,
  error: null,
  submitLabel: undefined
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'submit', payload: {
    amount: number
    method: PaymentMethod
    payment_date: string
    reference?: string
    notes?: string
  }): void
}>()

const { t } = useI18n()
const { format: formatCurrency } = useCurrency()

interface MethodOption {
  value: PaymentMethod
  icon: string
}

// India-only methods appear for clinics whose server-side country is IN
// (#365) — same gate as PaymentCreateModal / the payments list filter.
const clinicCountry = useClinicCountry()
const METHODS = computed<MethodOption[]>(() => [
  { value: 'cash', icon: 'i-lucide-banknote' },
  { value: 'card', icon: 'i-lucide-credit-card' },
  { value: 'bank_transfer', icon: 'i-lucide-landmark' },
  { value: 'direct_debit', icon: 'i-lucide-repeat' },
  { value: 'insurance', icon: 'i-lucide-shield' },
  ...(clinicCountry.value === 'IN'
    ? [
        { value: 'upi' as PaymentMethod, icon: 'i-lucide-smartphone-nfc' },
        { value: 'netbanking' as PaymentMethod, icon: 'i-lucide-landmark' }
      ]
    : []),
  { value: 'other', icon: 'i-lucide-more-horizontal' }
])

const todayIso = () => new Date().toISOString().slice(0, 10)

const buildInitial = () => ({
  amount: Math.max(0, Number(props.pendingAmount || 0)),
  method: 'cash' as PaymentMethod,
  payment_date: todayIso(),
  reference: '',
  notes: ''
})

const form = ref(buildInitial())
const showDetails = ref(false)

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    form.value = buildInitial()
    showDetails.value = false
  }
})

const pending = computed(() => Math.max(0, Number(props.pendingAmount || 0)))
const amount = computed(() => Number(form.value.amount || 0))
const isValid = computed(() => amount.value > 0)
const isToday = computed(() => form.value.payment_date === todayIso())

function fmt(value: number | string) {
  return formatCurrency(Number(value || 0))
}

function setAmount(v: number) {
  form.value.amount = Number(v.toFixed(2))
}

function setToday() {
  form.value.payment_date = todayIso()
}

function close() {
  emit('update:open', false)
}

function submit() {
  if (!isValid.value || props.submitting) return
  emit('submit', {
    amount: amount.value,
    method: form.value.method,
    payment_date: form.value.payment_date,
    reference: form.value.reference?.trim() || undefined,
    notes: form.value.notes?.trim() || undefined
  })
}

const submitText = computed(() => props.submitLabel ?? t('shared.collect.submit'))
</script>

<template>
  <UModal
    :open="open"
    :title="title"
    :description="subtitle"
    :ui="{
      content: 'max-h-[90vh] flex flex-col',
      body: 'overflow-y-auto'
    }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="space-y-5">
        <!-- Amount -->
        <section class="space-y-2">
          <label class="block text-sm font-medium text-default">
            {{ t('shared.collect.amountLabel') }}
          </label>
          <div class="relative">
            <span
              class="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-xl text-subtle"
            >
              {{ fmt(0).replace(/[\d.,]/g, '').trim() }}
            </span>
            <input
              v-model.number="form.amount"
              type="number"
              inputmode="decimal"
              step="0.01"
              min="0"
              class="w-full rounded-md border border-default bg-elevated py-3 pl-10 pr-3 text-2xl font-semibold text-default focus:border-primary-accent focus:outline-none focus:ring-1 focus:ring-primary-accent"
            >
          </div>
          <div
            v-if="pending > 0"
            class="flex flex-wrap gap-2"
          >
            <UButton
              size="xs"
              variant="soft"
              :color="amount === pending ? 'primary' : 'neutral'"
              @click="setAmount(pending)"
            >
              {{ t('shared.collect.quickFull') }} · {{ fmt(pending) }}
            </UButton>
            <UButton
              size="xs"
              variant="soft"
              color="neutral"
              @click="setAmount(pending / 2)"
            >
              50% · {{ fmt(pending / 2) }}
            </UButton>
            <UButton
              size="xs"
              variant="soft"
              color="neutral"
              @click="setAmount(pending / 4)"
            >
              25% · {{ fmt(pending / 4) }}
            </UButton>
          </div>
        </section>

        <!-- Method -->
        <section class="space-y-2">
          <label class="block text-sm font-medium text-default">
            {{ t('shared.collect.methodLabel') }}
          </label>
          <div class="grid grid-cols-3 gap-2">
            <button
              v-for="m in METHODS"
              :key="m.value"
              type="button"
              class="flex flex-col items-center gap-1 rounded-md border px-2 py-3 text-xs transition-all focus:outline-none focus:ring-1 focus:ring-primary-accent"
              :class="form.method === m.value
                ? 'border-primary-accent bg-primary-50 text-primary-accent dark:bg-primary-950'
                : 'border-default bg-elevated text-default hover:border-primary-accent'"
              @click="form.method = m.value"
            >
              <UIcon
                :name="m.icon"
                class="h-5 w-5"
              />
              <span>{{ t(`payments.methods.${m.value}`) }}</span>
            </button>
          </div>
        </section>

        <!-- Date -->
        <section class="space-y-2">
          <label class="block text-sm font-medium text-default">
            {{ t('shared.collect.dateLabel') }}
          </label>
          <div class="flex items-center gap-2">
            <UInput
              v-model="form.payment_date"
              type="date"
              class="flex-1"
            />
            <UButton
              v-if="!isToday"
              size="xs"
              variant="soft"
              color="neutral"
              @click="setToday"
            >
              {{ t('shared.collect.today') }}
            </UButton>
          </div>
        </section>

        <!-- Caller-supplied narration (e.g. allocation breakdown) -->
        <slot
          name="narration"
          :amount="amount"
          :pending="pending"
        />

        <!-- Optional details -->
        <section>
          <button
            type="button"
            class="flex items-center gap-1 text-sm text-subtle hover:text-default"
            @click="showDetails = !showDetails"
          >
            <UIcon
              :name="showDetails ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              class="h-4 w-4"
            />
            {{ t('shared.collect.optionalDetails') }}
          </button>
          <div
            v-if="showDetails"
            class="mt-3 space-y-3"
          >
            <UFormField :label="t('shared.collect.referenceLabel')">
              <UInput
                v-model="form.reference"
                :placeholder="t('shared.collect.referencePlaceholder')"
              />
            </UFormField>
            <UFormField :label="t('shared.collect.notesLabel')">
              <UInput v-model="form.notes" />
            </UFormField>
          </div>
        </section>

        <p
          v-if="error"
          class="text-sm text-red-600"
        >
          {{ error }}
        </p>
      </div>
    </template>

    <template #footer>
      <div class="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <UButton
          variant="ghost"
          color="neutral"
          :disabled="submitting"
          @click="close"
        >
          {{ t('shared.collect.cancel') }}
        </UButton>
        <UButton
          color="primary"
          size="lg"
          :loading="submitting"
          :disabled="!isValid || submitting"
          @click="submit"
        >
          <UIcon
            :name="submitIcon"
            class="mr-1 h-4 w-4"
          />
          {{ submitText }} {{ fmt(amount) }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>
