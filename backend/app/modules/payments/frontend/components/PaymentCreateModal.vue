<script setup lang="ts">
/**
 * Reusable "record payment" modal.
 *
 * Two call sites with very different ergonomics:
 *  - patient ``Pagos`` tab (PatientPaymentsPanel + PendingChargesCard): the
 *    patient is known, the amount is pre-filled to the pending balance,
 *    reception just confirms method.
 *  - admin ``/payments/new``: no defaults — admin picks patient and types
 *    everything in.
 *
 * UX optimised for the first flow (95% of usage). Advanced fields
 * (reference, notes, multi-target distribution) hide behind a
 * disclosure so the modal looks like a one-tap "cobrar" by default.
 */

import type {
  PaymentAllocationCreate,
  PaymentMethod,
  PaymentRecord
} from '~~/app/types'

const props = withDefaults(defineProps<{
  open: boolean
  defaultPatientId?: string
  /**
   * Display name of the patient when ``defaultPatientId`` is set —
   * shown read-only at the top of the modal. The host (PatientPaymentsPanel,
   * budget cards) already has the patient resolved; we never want to
   * surface a raw UUID to reception.
   */
  defaultPatientName?: string
  defaultBudgetId?: string
  defaultAmount?: number
  /** Visible label for the locked budget (e.g. ``PRES-2026-0001``). */
  budgetLabel?: string
  /**
   * Suggested amount to charge (typically the patient's ``clinic_receivable``).
   * When set, an inline hint offers to copy this value into the amount field.
   */
  suggestedAmount?: number
}>(), {
  defaultPatientId: '',
  defaultPatientName: '',
  defaultBudgetId: undefined,
  defaultAmount: 0,
  budgetLabel: undefined,
  suggestedAmount: undefined
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'created', payment: PaymentRecord): void
}>()

const { t } = useI18n()
const { create } = usePayments()
const { format: formatCurrency, symbol: currencySymbol } = useCurrency()

const isBudgetContext = computed(() => Boolean(props.defaultBudgetId))
const isPatientLocked = computed(() => Boolean(props.defaultPatientId))

// Primary methods rendered as chips. Less common ones live in a "more"
// disclosure to keep the default view scannable.
interface MethodOption {
  value: PaymentMethod
  icon: string
}
const PRIMARY_METHODS: MethodOption[] = [
  { value: 'cash', icon: 'i-lucide-banknote' },
  { value: 'card', icon: 'i-lucide-credit-card' },
  { value: 'bank_transfer', icon: 'i-lucide-building-2' },
  { value: 'insurance', icon: 'i-lucide-shield' }
]
const SECONDARY_METHODS: MethodOption[] = [
  { value: 'direct_debit', icon: 'i-lucide-repeat' },
  { value: 'other', icon: 'i-lucide-more-horizontal' }
]
const ALL_METHODS = [...PRIMARY_METHODS, ...SECONDARY_METHODS]

function buildInitialAllocations(): PaymentAllocationCreate[] {
  const amount = Number(props.defaultAmount ?? 0)
  if (isBudgetContext.value && props.defaultBudgetId) {
    return [{
      target_type: 'budget',
      target_id: props.defaultBudgetId,
      amount
    }]
  }
  return [{ target_type: 'on_account', target_id: undefined, amount }]
}

function buildInitialForm() {
  return {
    patient_id: props.defaultPatientId || '',
    amount: Number(props.defaultAmount ?? 0),
    method: 'cash' as PaymentMethod,
    payment_date: new Date().toISOString().slice(0, 10),
    reference: '',
    notes: '',
    allocations: buildInitialAllocations()
  }
}

const form = ref(buildInitialForm())
const formError = ref<string | null>(null)
const isSubmitting = ref(false)
const showAdvanced = ref(false)
const showSecondaryMethods = ref(false)
const splitManually = ref(false)
const amountInputRef = ref<HTMLInputElement | null>(null)

// Reset whenever the modal opens — keeps state from leaking between calls.
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    form.value = buildInitialForm()
    formError.value = null
    showAdvanced.value = false
    showSecondaryMethods.value = false
    splitManually.value = false
    await nextTick()
    amountInputRef.value?.focus()
    amountInputRef.value?.select()
  }
})

// When the user changes the importe and hasn't manually edited the
// allocation split, mirror the change into the single allocation so the
// "Σ = X / Y" mismatch can't lock the submit button silently.
watch(() => form.value.amount, (newAmount) => {
  if (splitManually.value) return
  if (form.value.allocations.length !== 1) return
  form.value.allocations[0].amount = Number(newAmount) || 0
})

const allocationsSum = computed(() =>
  form.value.allocations.reduce((s, a) => s + Number(a.amount || 0), 0)
)

const allocationsValid = computed(() => {
  const target = Number(form.value.amount)
  return Math.abs(allocationsSum.value - target) <= 0.001
})

const amountValid = computed(() => Number(form.value.amount) > 0)
const canSubmit = computed(() =>
  amountValid.value && allocationsValid.value && Boolean(form.value.patient_id)
)

const suggestedDiffers = computed(() => {
  if (props.suggestedAmount === undefined) return false
  return Math.abs(Number(form.value.amount) - props.suggestedAmount) > 0.001
})

const isToday = computed(() =>
  form.value.payment_date === new Date().toISOString().slice(0, 10)
)

function applySuggestion() {
  if (props.suggestedAmount === undefined) return
  form.value.amount = props.suggestedAmount
}

function pickMethod(method: PaymentMethod) {
  form.value.method = method
}

function addAllocation() {
  splitManually.value = true
  form.value.allocations.push({
    target_type: 'on_account',
    target_id: undefined,
    amount: 0
  })
}

function removeAllocation(idx: number) {
  if (form.value.allocations.length > 1) {
    form.value.allocations.splice(idx, 1)
  }
}

function onAllocationAmountInput() {
  splitManually.value = true
}

async function submit() {
  formError.value = null
  if (!form.value.patient_id) {
    formError.value = t('payments.new.errPatient')
    return
  }
  if (!amountValid.value) {
    formError.value = t('payments.new.errAmount')
    return
  }
  if (!allocationsValid.value) {
    formError.value = t('payments.new.errSum')
    return
  }

  isSubmitting.value = true
  try {
    const created = await create({
      patient_id: form.value.patient_id,
      amount: Number(form.value.amount),
      method: form.value.method,
      payment_date: form.value.payment_date,
      reference: form.value.reference || undefined,
      notes: form.value.notes || undefined,
      allocations: form.value.allocations.map(a => ({
        target_type: a.target_type,
        target_id: a.target_type === 'budget' ? a.target_id : undefined,
        amount: Number(a.amount)
      }))
    })
    if (created) {
      emit('created', created)
      emit('update:open', false)
    } else {
      formError.value = t('payments.new.errUnknown')
    }
  } finally {
    isSubmitting.value = false
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey && canSubmit.value) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <UModal
    :open="open"
    :title="t('payments.new.title')"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div
        class="space-y-5"
        @keydown="handleKeydown"
      >
        <!-- Patient header (read-only when locked). The admin flow at
             /payments/new is the only place where the picker stays an
             editable input — everywhere else we already know the patient. -->
        <div
          v-if="isPatientLocked"
          class="flex items-center gap-3 p-3 rounded-token-md bg-surface-muted"
        >
          <UAvatar
            :alt="defaultPatientName || ''"
            size="md"
            icon="i-lucide-user"
          />
          <div class="min-w-0">
            <div class="text-xs text-muted uppercase tracking-wide">
              {{ t('payments.new.patient') }}
            </div>
            <div class="font-medium truncate">
              {{ defaultPatientName || t('payments.new.unknownPatient') }}
            </div>
          </div>
        </div>
        <UFormField
          v-else
          :label="t('payments.new.patient')"
        >
          <UInput
            v-model="form.patient_id"
            :placeholder="t('payments.new.patientPlaceholder')"
          />
        </UFormField>

        <!-- Importe — hero field. Big, autofocused, currency suffix.
             Sub-line offers to snap to the suggested pending amount when
             the user typed something different. -->
        <div>
          <label class="block text-xs text-muted uppercase tracking-wide mb-1">
            {{ t('payments.new.amount') }}
          </label>
          <div class="relative">
            <input
              ref="amountInputRef"
              v-model.number="form.amount"
              type="number"
              step="0.01"
              min="0"
              inputmode="decimal"
              class="w-full text-3xl font-semibold py-3 px-4 pr-14 rounded-token-md border border-default bg-surface focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] tnum"
            >
            <span class="absolute right-4 top-1/2 -translate-y-1/2 text-xl text-muted pointer-events-none">{{ currencySymbol() }}</span>
          </div>
          <div
            v-if="suggestedAmount !== undefined && suggestedAmount > 0"
            class="mt-1 text-xs text-muted flex items-center gap-2"
          >
            <span>
              {{ t('payments.new.suggestedHint', { amount: formatCurrency(suggestedAmount) }) }}
            </span>
            <button
              v-if="suggestedDiffers"
              type="button"
              class="text-primary-accent hover:underline"
              @click="applySuggestion"
            >
              {{ t('payments.new.useSuggested') }}
            </button>
          </div>
        </div>

        <!-- Método — chips. One tap, no dropdown. -->
        <div>
          <label class="block text-xs text-muted uppercase tracking-wide mb-2">
            {{ t('payments.new.method') }}
          </label>
          <div class="flex flex-wrap gap-2">
            <button
              v-for="m in PRIMARY_METHODS"
              :key="m.value"
              type="button"
              class="method-chip"
              :class="{ active: form.method === m.value }"
              @click="pickMethod(m.value)"
            >
              <UIcon
                :name="m.icon"
                class="w-4 h-4"
              />
              <span>{{ t(`payments.methods.${m.value}`) }}</span>
            </button>
            <button
              v-if="!showSecondaryMethods && !SECONDARY_METHODS.some(m => m.value === form.method)"
              type="button"
              class="method-chip ghost"
              @click="showSecondaryMethods = true"
            >
              <UIcon
                name="i-lucide-plus"
                class="w-4 h-4"
              />
              <span>{{ t('payments.new.moreMethods') }}</span>
            </button>
            <button
              v-for="m in SECONDARY_METHODS"
              v-show="showSecondaryMethods || form.method === m.value"
              :key="m.value"
              type="button"
              class="method-chip"
              :class="{ active: form.method === m.value }"
              @click="pickMethod(m.value)"
            >
              <UIcon
                :name="m.icon"
                class="w-4 h-4"
              />
              <span>{{ t(`payments.methods.${m.value}`) }}</span>
            </button>
          </div>
        </div>

        <!-- Fecha — collapsed "Hoy" with click-to-expand for back-dating. -->
        <div>
          <label class="block text-xs text-muted uppercase tracking-wide mb-1">
            {{ t('payments.new.date') }}
          </label>
          <div class="flex items-center gap-2">
            <input
              v-model="form.payment_date"
              type="date"
              class="text-sm py-1.5 px-2 rounded-token-md border border-default bg-surface focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)]"
            >
            <UBadge
              v-if="isToday"
              color="success"
              variant="subtle"
              size="xs"
            >
              {{ t('payments.new.today') }}
            </UBadge>
          </div>
        </div>

        <!-- Avanzado: referencia, notas, distribución -->
        <div class="border-t border-default pt-3">
          <button
            type="button"
            class="flex items-center gap-1 text-sm text-muted hover:text-default"
            @click="showAdvanced = !showAdvanced"
          >
            <UIcon
              :name="showAdvanced ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              class="w-4 h-4"
            />
            <span>{{ t('payments.new.advanced') }}</span>
          </button>

          <div
            v-if="showAdvanced"
            class="mt-3 space-y-4"
          >
            <UFormField :label="t('payments.new.reference')">
              <UInput
                v-model="form.reference"
                :placeholder="t('payments.new.referencePlaceholder')"
              />
            </UFormField>

            <UFormField :label="t('payments.new.notes')">
              <UInput v-model="form.notes" />
            </UFormField>

            <div>
              <div class="mb-2 flex items-center justify-between">
                <div>
                  <div class="font-medium text-sm">
                    {{ t('payments.new.allocations') }}
                  </div>
                  <div class="text-xs text-muted">
                    {{ t('payments.new.allocationsHint') }}
                  </div>
                </div>
                <UButton
                  size="xs"
                  variant="ghost"
                  icon="i-lucide-plus"
                  @click="addAllocation"
                >
                  {{ t('payments.new.addAllocation') }}
                </UButton>
              </div>
              <div
                v-for="(a, idx) in form.allocations"
                :key="idx"
                class="mb-2 flex items-center gap-2"
              >
                <USelect
                  v-model="a.target_type"
                  :items="[
                    { label: t('payments.new.allocationOnAccount'), value: 'on_account' },
                    { label: t('payments.new.allocationToBudget'), value: 'budget' }
                  ]"
                  class="w-40"
                  :disabled="idx === 0 && isBudgetContext"
                />
                <UInput
                  v-if="a.target_type === 'budget'"
                  v-model="a.target_id"
                  :placeholder="budgetLabel || 'budget_id'"
                  :disabled="idx === 0 && isBudgetContext"
                  class="flex-1"
                />
                <UInput
                  v-model.number="a.amount"
                  type="number"
                  step="0.01"
                  class="w-32"
                  @input="onAllocationAmountInput"
                />
                <UButton
                  v-if="form.allocations.length > 1 && !(idx === 0 && isBudgetContext)"
                  size="xs"
                  variant="ghost"
                  icon="i-lucide-x"
                  @click="removeAllocation(idx)"
                />
              </div>
              <div
                v-if="form.allocations.length > 1 || splitManually"
                class="text-xs"
                :class="allocationsValid ? 'text-muted' : 'text-danger-accent font-medium'"
              >
                {{ t('payments.new.sumLabel') }}
                {{ formatCurrency(allocationsSum) }} /
                {{ formatCurrency(form.amount) }}
                <span v-if="!allocationsValid">— {{ t('payments.new.sumMismatch') }}</span>
              </div>
            </div>
          </div>
        </div>

        <p
          v-if="formError"
          class="text-sm text-danger-accent"
        >
          {{ formError }}
        </p>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          variant="ghost"
          @click="emit('update:open', false)"
        >
          {{ t('payments.new.cancel') }}
        </UButton>
        <UButton
          color="primary"
          icon="i-lucide-check"
          :loading="isSubmitting"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{
            amountValid
              ? t('payments.new.submitWithAmount', { amount: formatCurrency(form.amount) })
              : t('payments.new.submit')
          }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.method-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: var(--radius-md, 8px);
  border: 1px solid var(--color-border-default, #E5E7EB);
  background: var(--color-surface, #FFFFFF);
  font-size: 14px;
  font-weight: 500;
  color: var(--color-text-default, #1F2937);
  cursor: pointer;
  transition: all 120ms ease;
}

.method-chip:hover {
  background: var(--color-surface-muted, #F3F4F6);
}

.method-chip.active {
  background: var(--color-primary, #3B82F6);
  border-color: var(--color-primary, #3B82F6);
  color: white;
}

.method-chip.ghost {
  border-style: dashed;
  color: var(--color-text-muted, #6B7280);
}

.tnum {
  font-variant-numeric: tabular-nums;
}
</style>
