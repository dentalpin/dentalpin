<script setup lang="ts">
import type { InvoiceItem, Patient } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const toast = useToast()

const {
  currentInvoice,
  isLoading,
  fetchInvoice,
  updateInvoice,
  removeItem,
  canEdit,
  formatCurrency
} = useInvoices()

const invoiceId = computed(() => route.params.id as string)

// State
const isSaving = ref(false)
const selectedPatient = ref<Patient | null>(null)
const isChangingPatient = ref(false)

// Form data (no billing fields - billing comes from patient)
const form = ref({
  payment_term_days: 30,
  due_date: '',
  internal_notes: '',
  public_notes: ''
})

// Track deleted items
const deletedItemIds = ref<Set<string>>(new Set())

// Item modal state
const isItemModalOpen = ref(false)
const editingItem = ref<InvoiceItem | undefined>(undefined)

function openAddItemModal() {
  editingItem.value = undefined
  isItemModalOpen.value = true
}

function openEditItemModal(item: InvoiceItem) {
  editingItem.value = item
  isItemModalOpen.value = true
}

// Can change patient? Only for drafts without budget link
const canChangePatient = computed(() => {
  return currentInvoice.value?.status === 'draft' && !currentInvoice.value?.budget
})

// Get effective billing data (from patient for drafts)
// Use selectedPatient if changed, otherwise use invoice patient
const effectiveBillingData = computed(() => {
  const patient = selectedPatient.value || currentInvoice.value?.patient
  if (!patient) return null

  return {
    name: patient.billing_name || `${patient.first_name} ${patient.last_name}`,
    tax_id: patient.billing_tax_id || '',
    email: patient.billing_email || patient.email || '',
    address: patient.billing_address || null
  }
})

// When patient is selected via PatientSearch component
function handlePatientChange(patient: Patient | null) {
  selectedPatient.value = patient
  isChangingPatient.value = false
}

// Load invoice
onMounted(async () => {
  const invoice = await fetchInvoice(invoiceId.value)

  if (!invoice) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.notFound'),
      color: 'error'
    })
    router.push('/invoices')
    return
  }

  if (!canEdit(invoice)) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.cannotEdit'),
      color: 'error'
    })
    router.push(`/invoices/${invoiceId.value}`)
    return
  }

  // Populate form with invoice data (no billing fields)
  form.value = {
    payment_term_days: invoice.payment_term_days || 30,
    due_date: invoice.due_date?.split('T')[0] || '',
    internal_notes: invoice.internal_notes || '',
    public_notes: invoice.public_notes || ''
  }

  // Set selectedPatient for PatientSearch component
  if (invoice.patient) {
    selectedPatient.value = invoice.patient as Patient
  }
})

// Get current items (excluding deleted)
const currentItems = computed(() => {
  if (!currentInvoice.value?.items) return []
  return currentInvoice.value.items.filter(item => !deletedItemIds.value.has(item.id))
})

// Mark item for deletion
function markItemForDeletion(itemId: string) {
  deletedItemIds.value.add(itemId)
}

// Get item display name (from catalog if available)
function getItemName(item: InvoiceItem): string {
  if (item.catalog_item) {
    return item.catalog_item.names[locale.value] || item.catalog_item.names.es || item.catalog_item.internal_code
  }
  return item.description
}

// Handle item saved from modal (add or edit)
function handleItemSaved() {
  isItemModalOpen.value = false
  editingItem.value = undefined
  fetchInvoice(invoiceId.value) // Refresh invoice data
}

// Calculate totals (using server-side values, excluding deleted items)
const totals = computed(() => {
  let subtotal = 0
  let totalTax = 0

  currentItems.value.forEach((item) => {
    subtotal += Number(item.line_subtotal) - Number(item.line_discount)
    totalTax += Number(item.line_tax)
  })

  return {
    subtotal,
    totalTax,
    total: subtotal + totalTax
  }
})

// Save changes
async function handleSave() {
  if (currentItems.value.length === 0) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.itemsRequired'),
      color: 'error'
    })
    return
  }

  isSaving.value = true

  try {
    // 1. Update invoice details (no billing fields - comes from patient)
    const patientChanged = canChangePatient.value
      && selectedPatient.value?.id !== currentInvoice.value?.patient?.id

    await updateInvoice(invoiceId.value, {
      patient_id: patientChanged ? selectedPatient.value?.id : undefined,
      payment_term_days: form.value.payment_term_days,
      due_date: form.value.due_date || undefined,
      internal_notes: form.value.internal_notes || undefined,
      public_notes: form.value.public_notes || undefined
    })

    // 2. Delete removed items
    for (const itemId of deletedItemIds.value) {
      await removeItem(invoiceId.value, itemId)
    }

    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.updated'),
      color: 'success'
    })

    router.push(`/invoices/${invoiceId.value}`)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.update')),
      color: 'error'
    })
  } finally {
    isSaving.value = false
  }
}

function goBack() {
  router.push(`/invoices/${invoiceId.value}`)
}
</script>

<template>
  <div class="space-y-6">
    <!-- Loading state -->
    <div
      v-if="isLoading && !currentInvoice"
      class="space-y-4"
    >
      <USkeleton class="h-8 w-48" />
      <USkeleton class="h-64 w-full" />
    </div>

    <!-- Content -->
    <template v-else-if="currentInvoice">
      <!-- Header -->
      <div class="flex items-center gap-4">
        <UButton
          variant="ghost"
          color="neutral"
          icon="i-lucide-arrow-left"
          @click="goBack"
        />
        <h1 class="text-display text-default">
          {{ t('invoice.edit') }}: {{ currentInvoice.invoice_number || t('invoice.draftNoNumber') }}
        </h1>
      </div>

      <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <!-- Left column - Form -->
        <div class="lg:col-span-2 space-y-6">
          <!-- Patient info -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="font-semibold text-default">
                  {{ t('invoice.patient') }}
                </h3>
                <UBadge
                  v-if="!canChangePatient && currentInvoice.budget"
                  color="neutral"
                  variant="subtle"
                >
                  {{ t('invoice.linkedToBudget') }}
                </UBadge>
              </div>
            </template>

            <!-- Patient selector (for drafts without budget) -->
            <div v-if="canChangePatient">
              <!-- Show current patient with change button -->
              <div
                v-if="selectedPatient && !isChangingPatient"
                class="flex items-center justify-between"
              >
                <div>
                  <p class="font-medium text-default">
                    {{ selectedPatient.last_name }}, {{ selectedPatient.first_name }}
                  </p>
                  <p class="text-caption text-subtle">
                    {{ selectedPatient.email || '-' }}
                  </p>
                </div>
                <UButton
                  variant="outline"
                  color="neutral"
                  size="sm"
                  icon="i-lucide-repeat"
                  @click="isChangingPatient = true"
                >
                  {{ t('common.change') }}
                </UButton>
              </div>

              <!-- Patient search (shown when no patient or changing) -->
              <div v-else>
                <UFormField :label="t('invoice.selectPatient')">
                  <PatientVisualSelector
                    :model-value="selectedPatient"
                    @update:model-value="handlePatientChange"
                  />
                </UFormField>
                <UButton
                  v-if="isChangingPatient && selectedPatient"
                  variant="ghost"
                  color="neutral"
                  size="sm"
                  class="mt-2"
                  @click="isChangingPatient = false"
                >
                  {{ t('common.cancel') }}
                </UButton>
              </div>
            </div>

            <!-- Current patient display (read-only when linked to budget) -->
            <div
              v-else-if="currentInvoice.patient"
              class="flex items-center justify-between"
            >
              <div>
                <p class="font-medium text-default">
                  {{ currentInvoice.patient.last_name }}, {{ currentInvoice.patient.first_name }}
                </p>
                <p class="text-caption text-subtle">
                  {{ currentInvoice.patient.email || '-' }}
                </p>
              </div>
            </div>
          </UCard>

          <!-- Billing data (from patient - read-only) -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="font-semibold text-default">
                  {{ t('invoice.billingData') }}
                </h3>
                <div class="flex items-center gap-2">
                  <UBadge
                    color="info"
                    variant="subtle"
                  >
                    {{ t('invoice.fromPatient') }}
                  </UBadge>
                  <UButton
                    v-if="currentInvoice?.patient?.id"
                    variant="ghost"
                    color="neutral"
                    size="xs"
                    icon="i-lucide-external-link"
                    :to="`/patients/${currentInvoice.patient.id}?tab=billing&returnTo=${encodeURIComponent(route.fullPath)}`"
                  >
                    {{ t('invoice.editInPatient') }}
                  </UButton>
                </div>
              </div>
            </template>

            <div
              v-if="effectiveBillingData"
              class="space-y-3"
            >
              <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p class="text-caption text-subtle">
                    {{ t('invoice.billingName') }}
                  </p>
                  <p class="font-medium text-default">
                    {{ effectiveBillingData.name || '-' }}
                  </p>
                </div>
                <div>
                  <p class="text-caption text-subtle">
                    {{ t('invoice.taxId') }}
                  </p>
                  <p class="font-medium text-default">
                    {{ effectiveBillingData.tax_id || '-' }}
                  </p>
                </div>
                <div>
                  <p class="text-caption text-subtle">
                    {{ t('invoice.billingEmail') }}
                  </p>
                  <p class="font-medium text-default">
                    {{ effectiveBillingData.email || '-' }}
                  </p>
                </div>
                <div v-if="effectiveBillingData.address">
                  <p class="text-caption text-subtle">
                    {{ t('invoice.billingAddress') }}
                  </p>
                  <p class="font-medium text-default">
                    {{ effectiveBillingData.address.street }},
                    {{ effectiveBillingData.address.postal_code }} {{ effectiveBillingData.address.city }}
                  </p>
                </div>
              </div>

              <p class="text-caption text-subtle italic">
                {{ t('invoice.billingFromPatientHint') }}
              </p>
            </div>
            <div v-else>
              <p class="text-caption text-subtle">
                {{ t('invoice.noBillingData') }}
              </p>
            </div>
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

          <!-- Items -->
          <UCard>
            <template #header>
              <div class="flex items-center justify-between">
                <h3 class="font-semibold text-default">
                  {{ t('invoice.items') }}
                </h3>
                <UButton
                  icon="i-lucide-plus"
                  size="sm"
                  @click="openAddItemModal"
                >
                  {{ t('invoice.addItem') }}
                </UButton>
              </div>
            </template>

            <!-- Empty state -->
            <div
              v-if="currentItems.length === 0"
              class="text-center py-8 text-subtle"
            >
              {{ t('budget.items.empty') }}
            </div>

            <!-- Items list (budget-style display) -->
            <div
              v-else
              class="divide-y divide-[var(--color-border-subtle)]"
            >
              <div
                v-for="item in currentItems"
                :key="item.id"
                class="py-4 flex items-start gap-4 cursor-pointer hover:bg-surface-muted -mx-4 px-4 transition-colors"
                @click="openEditItemModal(item)"
              >
                <div class="flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-default">
                      {{ getItemName(item) }}
                    </span>
                    <span
                      v-if="item.tooth_number"
                      class="text-caption text-subtle"
                    >
                      #{{ item.tooth_number }}
                      <span v-if="item.surfaces?.length">({{ item.surfaces.join(', ') }})</span>
                    </span>
                  </div>
                  <div class="text-caption text-subtle mt-1">
                    {{ item.quantity }} x {{ formatCurrency(item.unit_price) }}
                    <span
                      v-if="item.line_discount > 0"
                      class="text-success-accent"
                    >
                      -{{ formatCurrency(item.line_discount) }}
                    </span>
                  </div>
                  <p
                    v-if="item.catalog_item?.internal_code"
                    class="text-xs text-subtle mt-1"
                  >
                    {{ item.catalog_item.internal_code }}
                  </p>
                </div>
                <div class="text-right">
                  <p class="font-semibold text-default">
                    {{ formatCurrency(item.line_total) }}
                  </p>
                </div>
                <UButton
                  variant="ghost"
                  color="neutral"
                  icon="i-lucide-pencil"
                  size="sm"
                  @click.stop="openEditItemModal(item)"
                />
                <UButton
                  variant="ghost"
                  color="error"
                  icon="i-lucide-trash-2"
                  size="sm"
                  @click.stop="markItemForDeletion(item.id)"
                />
              </div>
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
              <div class="flex justify-between">
                <span class="text-subtle">{{ t('invoice.subtotal') }}</span>
                <span class="font-medium">{{ formatCurrency(totals.subtotal) }}</span>
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
                :loading="isSaving"
                @click="handleSave"
              >
                {{ t('common.save') }}
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
        </div>
      </div>
    </template>

    <!-- Item Modal (Add/Edit) -->
    <InvoiceItemModal
      v-model:open="isItemModalOpen"
      :invoice-id="invoiceId"
      :edit-item="editingItem"
      @saved="handleItemSaved"
    />
  </div>
</template>
