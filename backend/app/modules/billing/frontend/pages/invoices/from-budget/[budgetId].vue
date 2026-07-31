<script setup lang="ts">
import type { BudgetDetail, BudgetItem, InvoiceItemFromBudget, VatType } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const { fetchBudget } = useBudgets()
const { createFromBudget } = useInvoices()
const api = useApi()

const budgetId = route.params.budgetId as string

// State
const isLoading = ref(true)
const isSubmitting = ref(false)
const budget = ref<BudgetDetail | null>(null)
const vatTypes = ref<VatType[]>([])

// Selected items with quantities to invoice
const selectedItems = ref<Map<string, number>>(new Map())

// Form data (no billing fields - billing comes from patient)
const form = ref({
  payment_term_days: 30,
  due_date: '',
  internal_notes: '',
  public_notes: ''
})

// Load budget and VAT types
onMounted(async () => {
  try {
    const [budgetData, vatResponse] = await Promise.all([
      fetchBudget(budgetId),
      api.get<{ data: VatType[] }>('/api/v1/catalog/vat-types')
    ])

    budget.value = budgetData
    vatTypes.value = vatResponse.data

    // Pre-select all items that have available quantity
    // All items are invoiceable once budget is accepted (no item-level rejection)
    if (budgetData?.items) {
      budgetData.items.forEach((item) => {
        const availableQty = getAvailableQuantity(item)
        if (availableQty > 0) {
          selectedItems.value.set(item.id, availableQty)
        }
      })
    }
  } catch (e) {
    console.error('Failed to load budget:', e)
    toast.add({
      title: t('common.error'),
      description: t('budget.errors.notFound'),
      color: 'error'
    })
    router.push('/invoices')
  } finally {
    isLoading.value = false
  }
})

// Get available quantity to invoice (total - already invoiced)
function getAvailableQuantity(item: BudgetItem): number {
  return item.quantity - (item.invoiced_quantity || 0)
}

// Check if item is invoiceable (has available quantity)
// All items are invoiceable once budget is accepted (regardless of treatment status)
function isInvoiceable(item: BudgetItem): boolean {
  return getAvailableQuantity(item) > 0
}

// Toggle item selection
function toggleItem(item: BudgetItem) {
  if (selectedItems.value.has(item.id)) {
    selectedItems.value.delete(item.id)
  } else {
    selectedItems.value.set(item.id, getAvailableQuantity(item))
  }
}

// Update quantity for an item
function updateQuantity(itemId: string, quantity: number) {
  const item = budget.value?.items.find(i => i.id === itemId)
  if (!item) return

  const maxQty = getAvailableQuantity(item)
  const validQty = Math.max(1, Math.min(quantity, maxQty))
  selectedItems.value.set(itemId, validQty)
}

// Select all invoiceable items
function selectAll() {
  budget.value?.items.forEach((item) => {
    if (isInvoiceable(item)) {
      selectedItems.value.set(item.id, getAvailableQuantity(item))
    }
  })
}

// Deselect all items
function deselectAll() {
  selectedItems.value.clear()
}

// Get VAT type info
function getVatType(vatTypeId?: string): VatType | undefined {
  return vatTypes.value.find(v => v.id === vatTypeId)
}

// Calculate item line total (for preview)
function calculateItemTotal(item: BudgetItem, quantity: number): number {
  const subtotal = item.unit_price * quantity
  let discount = 0
  if (item.discount_value) {
    discount = item.discount_type === 'percentage'
      ? subtotal * (item.discount_value / 100)
      : item.discount_value
  }
  const taxableAmount = subtotal - discount
  const tax = taxableAmount * (item.vat_rate / 100)
  return taxableAmount + tax
}

// Calculate totals for selected items
const totals = computed(() => {
  let subtotal = 0
  let totalDiscount = 0
  let totalTax = 0

  selectedItems.value.forEach((quantity, itemId) => {
    const item = budget.value?.items.find(i => i.id === itemId)
    if (!item) return

    const lineSubtotal = item.unit_price * quantity
    let lineDiscount = 0
    if (item.discount_value) {
      lineDiscount = item.discount_type === 'percentage'
        ? lineSubtotal * (item.discount_value / 100)
        : item.discount_value * (quantity / item.quantity) // Prorate absolute discount
    }
    const lineTaxable = lineSubtotal - lineDiscount
    const lineTax = lineTaxable * (item.vat_rate / 100)

    subtotal += lineSubtotal
    totalDiscount += lineDiscount
    totalTax += lineTax
  })

  return {
    subtotal,
    totalDiscount,
    totalTax,
    total: subtotal - totalDiscount + totalTax
  }
})

// Format currency — clinic-wide.
const { format: formatCurrency } = useCurrency()

// Submit
async function handleSubmit() {
  if (selectedItems.value.size === 0) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.itemsRequired'),
      color: 'error'
    })
    return
  }

  isSubmitting.value = true

  try {
    const items: InvoiceItemFromBudget[] = Array.from(selectedItems.value.entries()).map(
      ([budget_item_id, quantity]) => ({ budget_item_id, quantity })
    )

    // Billing data comes from patient (not stored until invoice is issued)
    const invoice = await createFromBudget(budgetId, {
      items,
      payment_term_days: form.value.payment_term_days,
      due_date: form.value.due_date || undefined,
      internal_notes: form.value.internal_notes || undefined,
      public_notes: form.value.public_notes || undefined
    })

    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.created'),
      color: 'success'
    })

    router.push(`/invoices/${invoice.id}`)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.create')),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

function goBack() {
  router.push(`/budgets/${budgetId}`)
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <UButton
        variant="ghost"
        color="neutral"
        icon="i-lucide-arrow-left"
        @click="goBack"
      />
      <div>
        <h1 class="text-display text-default">
          {{ t('invoice.fromBudget') }}
        </h1>
        <p
          v-if="budget"
          class="text-caption text-subtle"
        >
          {{ budget.budget_number }} - {{ budget.patient?.last_name }}, {{ budget.patient?.first_name }}
        </p>
      </div>
    </div>

    <!-- Loading -->
    <div
      v-if="isLoading"
      class="space-y-4"
    >
      <USkeleton class="h-32 w-full" />
      <USkeleton class="h-64 w-full" />
    </div>

    <!-- Content -->
    <div
      v-else-if="budget"
      class="grid grid-cols-1 lg:grid-cols-3 gap-6"
    >
      <!-- Left column - Items selection -->
      <div class="lg:col-span-2 space-y-6">
        <!-- Items selection -->
        <UCard>
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="font-semibold text-default">
                {{ t('invoice.selectItems') }}
              </h3>
              <div class="flex gap-2">
                <UButton
                  variant="ghost"
                  size="sm"
                  @click="selectAll"
                >
                  {{ t('common.selectAll') }}
                </UButton>
                <UButton
                  variant="ghost"
                  size="sm"
                  @click="deselectAll"
                >
                  {{ t('common.deselectAll') }}
                </UButton>
              </div>
            </div>
          </template>

          <p class="text-caption text-subtle mb-4">
            {{ t('invoice.selectItemsHint') }}
          </p>

          <div class="divide-y divide-[var(--color-border-subtle)]">
            <div
              v-for="item in budget.items"
              :key="item.id"
              class="py-4"
              :class="{
                'opacity-50': !isInvoiceable(item)
              }"
            >
              <div class="flex items-start gap-4">
                <!-- Checkbox -->
                <div class="pt-1">
                  <UCheckbox
                    :model-value="selectedItems.has(item.id)"
                    :disabled="!isInvoiceable(item)"
                    @update:model-value="toggleItem(item)"
                  />
                </div>

                <!-- Item info -->
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-default">
                      {{ item.catalog_item?.name || 'Tratamiento' }}
                    </span>
                    <UBadge
                      v-if="item.tooth_number"
                      variant="subtle"
                      color="neutral"
                      size="xs"
                    >
                      {{ t('odontogram.tooth') }} {{ item.tooth_number }}
                    </UBadge>
                  </div>

                  <div class="mt-1 flex flex-wrap items-center gap-4 text-caption text-subtle">
                    <span>{{ formatCurrency(item.unit_price) }} x {{ item.quantity }}</span>
                    <span v-if="item.discount_value">
                      {{ t('invoice.discount') }}: {{ item.discount_type === 'percentage' ? `${item.discount_value}%` : formatCurrency(item.discount_value) }}
                    </span>
                    <span>{{ getVatType(item.vat_type_id)?.names[locale] || 'IVA' }} {{ item.vat_rate }}%</span>
                  </div>

                  <!-- Invoicing status -->
                  <div class="mt-2 flex items-center gap-4 text-xs">
                    <span
                      v-if="item.invoiced_quantity > 0"
                      class="text-warning-accent"
                    >
                      {{ t('invoice.alreadyInvoiced') }}: {{ item.invoiced_quantity }} / {{ item.quantity }}
                    </span>
                    <span
                      v-if="!isInvoiceable(item)"
                      class="text-danger-accent"
                    >
                      {{ t('invoice.availableQuantity') }}: 0
                    </span>
                  </div>
                </div>

                <!-- Quantity selector -->
                <div
                  v-if="selectedItems.has(item.id)"
                  class="flex items-center gap-2"
                >
                  <span class="text-caption text-subtle">{{ t('invoice.quantityToInvoice') }}:</span>
                  <UInput
                    :model-value="selectedItems.get(item.id)"
                    type="number"
                    :min="1"
                    :max="getAvailableQuantity(item)"
                    class="w-20"
                    @update:model-value="(val: string | number) => updateQuantity(item.id, Number(val))"
                  />
                  <span class="text-sm text-subtle">
                    / {{ getAvailableQuantity(item) }}
                  </span>
                </div>

                <!-- Line total -->
                <div class="text-right">
                  <span
                    v-if="selectedItems.has(item.id)"
                    class="font-semibold text-default"
                  >
                    {{ formatCurrency(calculateItemTotal(item, selectedItems.get(item.id) || 0)) }}
                  </span>
                  <span
                    v-else
                    class="text-subtle"
                  >
                    {{ formatCurrency(item.line_total) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </UCard>

        <!-- Billing data (from patient - read-only) -->
        <UCard v-if="budget?.patient">
          <template #header>
            <div class="flex items-center justify-between">
              <h3 class="font-semibold text-default">
                {{ t('invoice.billingData') }}
              </h3>
              <UBadge
                color="info"
                variant="subtle"
              >
                {{ t('invoice.fromPatient') }}
              </UBadge>
            </div>
          </template>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <p class="text-caption text-subtle">
                {{ t('invoice.billingName') }}
              </p>
              <p class="font-medium text-default">
                {{ budget.patient.billing_name || `${budget.patient.first_name} ${budget.patient.last_name}` }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('invoice.taxId') }}
              </p>
              <p class="font-medium text-default">
                {{ budget.patient.billing_tax_id || '-' }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('invoice.billingEmail') }}
              </p>
              <p class="font-medium text-default">
                {{ budget.patient.billing_email || budget.patient.email || '-' }}
              </p>
            </div>
            <div v-if="budget.patient.billing_address">
              <p class="text-caption text-subtle">
                {{ t('invoice.billingAddress') }}
              </p>
              <p class="font-medium text-default">
                {{ budget.patient.billing_address.street }},
                {{ budget.patient.billing_address.postal_code }} {{ budget.patient.billing_address.city }}
              </p>
            </div>
          </div>

          <p class="mt-4 text-caption text-subtle italic">
            {{ t('invoice.billingFromPatientHint') }}
          </p>
        </UCard>

        <!-- Payment terms -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('invoice.paymentTerms') }}
            </h3>
          </template>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UFormField :label="t('invoice.paymentTermDays')">
              <UInput
                v-model.number="form.payment_term_days"
                type="number"
                :min="0"
              />
            </UFormField>

            <UFormField :label="t('invoice.dueDate')">
              <UInput
                v-model="form.due_date"
                type="date"
              />
            </UFormField>
          </div>
        </UCard>

        <!-- Notes -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('invoice.notes') }}
            </h3>
          </template>

          <div class="space-y-4">
            <UFormField :label="t('invoice.publicNotes')">
              <UTextarea
                v-model="form.public_notes"
                :rows="2"
                :placeholder="t('invoice.publicNotesPlaceholder')"
              />
            </UFormField>

            <UFormField :label="t('invoice.internalNotes')">
              <UTextarea
                v-model="form.internal_notes"
                :rows="2"
                :placeholder="t('invoice.internalNotesPlaceholder')"
              />
            </UFormField>
          </div>
        </UCard>
      </div>

      <!-- Right column - Summary -->
      <div class="space-y-6">
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('invoice.summary') }}
            </h3>
          </template>

          <div class="space-y-3">
            <div class="flex justify-between text-sm">
              <span class="text-subtle">{{ t('invoice.items') }}:</span>
              <span class="font-medium">{{ selectedItems.size }}</span>
            </div>

            <div class="flex justify-between">
              <span class="text-subtle">{{ t('invoice.subtotal') }}</span>
              <span class="font-medium">{{ formatCurrency(totals.subtotal) }}</span>
            </div>

            <div
              v-if="totals.totalDiscount > 0"
              class="flex justify-between"
            >
              <span class="text-subtle">{{ t('invoice.discount') }}</span>
              <span class="font-medium text-success-accent">-{{ formatCurrency(totals.totalDiscount) }}</span>
            </div>

            <div class="flex justify-between">
              <span class="text-subtle">{{ t('invoice.tax') }}</span>
              <span class="font-medium">{{ formatCurrency(totals.totalTax) }}</span>
            </div>

            <div class="flex justify-between pt-3 border-t border-default">
              <span class="font-semibold text-default">{{ t('invoice.total') }}</span>
              <span class="font-bold text-lg text-default">
                {{ formatCurrency(totals.total) }}
              </span>
            </div>
          </div>

          <div class="mt-6 space-y-3">
            <UButton
              block
              color="primary"
              :loading="isSubmitting"
              :disabled="selectedItems.size === 0"
              @click="handleSubmit"
            >
              {{ t('invoice.createDraft') }}
            </UButton>
            <UButton
              block
              variant="outline"
              color="neutral"
              @click="goBack"
            >
              {{ t('common.cancel') }}
            </UButton>
          </div>
        </UCard>

        <!-- Budget info -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('budget.title') }}
            </h3>
          </template>

          <div class="space-y-2 text-sm">
            <div class="flex justify-between">
              <span class="text-subtle">{{ t('budget.budgetNumber') }}</span>
              <span class="font-medium">{{ budget.budget_number }}</span>
            </div>
            <div class="flex justify-between">
              <span class="text-subtle">{{ t('budget.status.title') }}</span>
              <UBadge
                variant="subtle"
                size="xs"
              >
                {{ t(`budget.status.${budget.status}`) }}
              </UBadge>
            </div>
            <div class="flex justify-between">
              <span class="text-subtle">{{ t('budget.total') }}</span>
              <span class="font-medium">{{ formatCurrency(budget.total) }}</span>
            </div>
          </div>
        </UCard>
      </div>
    </div>
  </div>
</template>
