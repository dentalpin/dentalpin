<script setup lang="ts">
import type { InvoiceItemCreate, Patient, VatType } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const toast = useToast()
const { createInvoice } = useInvoices()
const api = useApi()

// Track if coming from patient page
const comesFromPatient = computed(() => route.query.from === 'patient' && route.query.patient_id)
const backLabel = computed(() => comesFromPatient.value ? t('actions.back') : t('invoice.title'))

// State
const isLoading = ref(false)
const vatTypes = ref<VatType[]>([])
const selectedPatient = ref<Patient | null>(null)

// Form data
const form = ref({
  patient_id: '',
  billing_name: '',
  billing_tax_id: '',
  billing_email: '',
  billing_address: {
    street: '',
    city: '',
    postal_code: '',
    province: '',
    country: 'ES'
  },
  payment_term_days: 30,
  due_date: '',
  internal_notes: '',
  public_notes: ''
})

// Items
const items = ref<InvoiceItemCreate[]>([])

// Item modal state
const isItemModalOpen = ref(false)

function openAddItemModal() {
  isItemModalOpen.value = true
}

function handleItemAdded(item: InvoiceItemCreate) {
  items.value.push({
    ...item,
    display_order: items.value.length
  })
}

// Load VAT types
onMounted(async () => {
  try {
    const response = await api.get<{ data: VatType[] }>('/api/v1/catalog/vat-types')
    vatTypes.value = response.data
  } catch (e) {
    console.error('Failed to load VAT types:', e)
  }
})

// When patient is selected
function handlePatientSelect(patient: Patient | null) {
  selectedPatient.value = patient
  if (patient) {
    form.value.patient_id = patient.id
    // Auto-populate billing data: 1. Patient billing fields, 2. Patient personal info
    form.value.billing_name = patient.billing_name || `${patient.first_name} ${patient.last_name}`
    form.value.billing_tax_id = patient.billing_tax_id || ''
    form.value.billing_email = patient.billing_email || patient.email || ''
    if (patient.billing_address) {
      form.value.billing_address = { ...patient.billing_address }
    }
  } else {
    form.value.patient_id = ''
    form.value.billing_name = ''
    form.value.billing_tax_id = ''
    form.value.billing_email = ''
  }
}

// Remove item
function removeItem(index: number) {
  items.value.splice(index, 1)
  // Update display order
  items.value.forEach((item, i) => {
    item.display_order = i
  })
}

// Calculate item total
function getItemTotal(item: InvoiceItemCreate): number {
  const subtotal = item.unit_price * (item.quantity || 1)
  const vatType = vatTypes.value.find(v => v.id === item.vat_type_id)
  const vatRate = vatType?.rate || 0
  const tax = subtotal * (vatRate / 100)
  return subtotal + tax
}

// Calculate totals
const totals = computed(() => {
  let subtotal = 0
  let totalTax = 0

  items.value.forEach((item) => {
    const itemSubtotal = item.unit_price * (item.quantity || 1)
    const vatType = vatTypes.value.find(v => v.id === item.vat_type_id)
    const vatRate = vatType?.rate || 0
    const tax = itemSubtotal * (vatRate / 100)

    subtotal += itemSubtotal
    totalTax += tax
  })

  return {
    subtotal,
    totalTax,
    total: subtotal + totalTax
  }
})

// Format currency — clinic-wide.
const { format: formatCurrency } = useCurrency()

// Submit
async function handleSubmit() {
  if (!form.value.patient_id) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.patientRequired'),
      color: 'error'
    })
    return
  }

  if (items.value.length === 0) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.itemsRequired'),
      color: 'error'
    })
    return
  }

  isLoading.value = true

  try {
    const invoice = await createInvoice({
      patient_id: form.value.patient_id,
      billing_name: form.value.billing_name || undefined,
      billing_tax_id: form.value.billing_tax_id || undefined,
      billing_email: form.value.billing_email || undefined,
      billing_address: form.value.billing_address.street ? form.value.billing_address : undefined,
      payment_term_days: form.value.payment_term_days,
      due_date: form.value.due_date || undefined,
      internal_notes: form.value.internal_notes || undefined,
      public_notes: form.value.public_notes || undefined,
      items: items.value
    })

    toast.add({
      title: t('common.success'),
      description: t('invoice.messages.created'),
      color: 'success'
    })

    // Preserve patient context
    const queryParams = comesFromPatient.value
      ? `?from=patient&patientId=${route.query.patient_id}`
      : ''
    router.push(`/invoices/${invoice.id}${queryParams}`)
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('invoice.errors.create')),
      color: 'error'
    })
  } finally {
    isLoading.value = false
  }
}

function goBack() {
  if (comesFromPatient.value) {
    router.push(`/patients/${route.query.patient_id}`)
  } else {
    router.push('/invoices')
  }
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
      >
        {{ backLabel }}
      </UButton>
      <h1 class="text-display text-default">
        {{ t('invoice.new') }}
      </h1>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Left column - Form -->
      <div class="lg:col-span-2 space-y-6">
        <!-- Patient selection -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('invoice.patient') }}
            </h3>
          </template>

          <PatientVisualSelector
            :model-value="selectedPatient"
            @update:model-value="handlePatientSelect"
          />

          <!-- Billing info badges -->
          <div
            v-if="selectedPatient"
            class="mt-2 flex items-center gap-2"
          >
            <UBadge
              v-if="selectedPatient.has_complete_billing_info"
              color="success"
              variant="subtle"
              size="xs"
            >
              <UIcon
                name="i-lucide-check"
                class="w-3 h-3 mr-1"
              />
              {{ t('invoice.billingDataComplete') }}
            </UBadge>
            <UBadge
              v-else
              color="warning"
              variant="subtle"
              size="xs"
            >
              <UIcon
                name="i-lucide-alert-triangle"
                class="w-3 h-3 mr-1"
              />
              {{ t('invoice.billingDataIncomplete') }}
            </UBadge>
          </div>
          <p
            v-if="selectedPatient && !selectedPatient.has_complete_billing_info"
            class="text-xs text-warning-accent mt-1"
          >
            {{ t('invoice.billingDataIncompleteHint') }}
            <NuxtLink
              :to="`/patients/${selectedPatient.id}`"
              class="underline"
            >
              {{ t('invoice.editPatientBilling') }}
            </NuxtLink>
          </p>
        </UCard>

        <!-- Billing data -->
        <UCard>
          <template #header>
            <h3 class="font-semibold text-default">
              {{ t('invoice.billingData') }}
            </h3>
          </template>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <UFormField :label="t('invoice.billingName')">
              <UInput v-model="form.billing_name" />
            </UFormField>

            <UFormField :label="t('invoice.taxId')">
              <UInput
                v-model="form.billing_tax_id"
                placeholder="NIF/CIF"
              />
            </UFormField>

            <UFormField :label="t('invoice.billingEmail')">
              <UInput
                v-model="form.billing_email"
                type="email"
              />
            </UFormField>

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
            v-if="items.length === 0"
            class="text-center py-8 text-subtle"
          >
            <UIcon
              name="i-lucide-file-text"
              class="w-12 h-12 mx-auto mb-3 text-subtle"
            />
            <p>{{ t('budget.items.empty') }}</p>
            <UButton
              variant="outline"
              class="mt-3"
              icon="i-lucide-plus"
              @click="openAddItemModal"
            >
              {{ t('invoice.addItem') }}
            </UButton>
          </div>

          <!-- Items list -->
          <div
            v-else
            class="divide-y divide-[var(--color-border-subtle)]"
          >
            <div
              v-for="(item, index) in items"
              :key="index"
              class="py-4 flex items-start gap-4"
            >
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-default">
                    {{ item.description }}
                  </span>
                  <span
                    v-if="item.tooth_number"
                    class="text-caption text-subtle"
                  >
                    #{{ item.tooth_number }}
                    <span v-if="item.surfaces?.length">({{ item.surfaces.join(', ') }})</span>
                  </span>
                </div>
                <p class="text-caption text-subtle mt-1">
                  {{ item.quantity }} x {{ formatCurrency(item.unit_price) }}
                  <span
                    v-if="item.discount_value"
                    class="text-success-accent"
                  >
                    - {{ item.discount_type === 'percentage' ? `${item.discount_value}%` : formatCurrency(item.discount_value) }}
                  </span>
                </p>
                <p
                  v-if="item.internal_code"
                  class="text-xs text-subtle mt-1"
                >
                  {{ item.internal_code }}
                </p>
              </div>
              <div class="text-right">
                <p class="font-semibold text-default">
                  {{ formatCurrency(getItemTotal(item)) }}
                </p>
              </div>
              <UButton
                variant="ghost"
                color="error"
                icon="i-lucide-trash-2"
                size="sm"
                @click="removeItem(index)"
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
              :loading="isLoading"
              :disabled="!form.patient_id || items.length === 0"
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
      </div>
    </div>

    <!-- Add Item Modal -->
    <NewInvoiceItemModal
      v-model:open="isItemModalOpen"
      @added="handleItemAdded"
    />
  </div>
</template>
