<script setup lang="ts">
import type { InvoiceItem, InvoiceItemCreate, TreatmentCatalogItem, VatType } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const props = defineProps<{
  invoiceId: string
  editItem?: InvoiceItem // If provided, modal is in edit mode
}>()

const open = defineModel<boolean>('open', { default: false })

const emit = defineEmits<{
  saved: [] // Emitted on both add and update
}>()

const { t, locale } = useI18n()
const toast = useToast()
const api = useApi()
const { getItemName, formatPrice } = useCatalog()
const { addItem, updateItem } = useInvoices()

// Edit mode
const isEditing = computed(() => !!props.editItem)

// VAT types
const vatTypes = ref<VatType[]>([])
const isLoadingVat = ref(false)

// Selection state
const selectedItem = ref<TreatmentCatalogItem | null>(null)

// Item form
const form = reactive<InvoiceItemCreate>({
  description: '',
  catalog_item_id: undefined,
  unit_price: 0,
  quantity: 1,
  vat_type_id: undefined,
  tooth_number: undefined,
  surfaces: [],
  discount_type: undefined,
  discount_value: undefined
})

const isSubmitting = ref(false)

// Load VAT types
async function loadVatTypes() {
  if (vatTypes.value.length > 0) return
  isLoadingVat.value = true
  try {
    const response = await api.get<{ data: VatType[] }>('/api/v1/catalog/vat-types')
    vatTypes.value = response.data
  } catch {
    console.error('Failed to load VAT types')
  } finally {
    isLoadingVat.value = false
  }
}

// VAT type options
const vatTypeOptions = computed(() =>
  vatTypes.value
    .filter(v => v.is_active)
    .map(v => ({
      label: `${v.names[locale.value] || v.names.es || 'IVA'} (${v.rate}%)`,
      value: v.id
    }))
)

function handleItemSelect(item: TreatmentCatalogItem | null) {
  selectedItem.value = item
  if (item) {
    form.catalog_item_id = item.id
    form.description = getItemName(item)
    form.unit_price = item.default_price || 0
    // Set default VAT type
    const defaultVat = vatTypes.value.find(v => v.is_default)
    if (defaultVat) {
      form.vat_type_id = defaultVat.id
    }
  } else {
    form.catalog_item_id = undefined
    form.description = ''
    form.unit_price = 0
  }
}

// Tooth surfaces
const toothSurfaces = ['M', 'O', 'D', 'V', 'L', 'P', 'I']

function toggleSurface(surface: string) {
  if (!form.surfaces) form.surfaces = []
  const index = form.surfaces.indexOf(surface)
  if (index >= 0) {
    form.surfaces.splice(index, 1)
  } else {
    form.surfaces.push(surface)
  }
}

// Calculate preview total
const previewTotal = computed(() => {
  const subtotal = form.unit_price * (form.quantity || 1)

  let discountedSubtotal = subtotal
  if (form.discount_type && form.discount_value) {
    if (form.discount_type === 'percentage') {
      discountedSubtotal = subtotal * (1 - form.discount_value / 100)
    } else {
      discountedSubtotal = subtotal - form.discount_value
    }
  }

  // Add VAT
  const vatType = vatTypes.value.find(v => v.id === form.vat_type_id)
  const vatRate = vatType?.rate || 0
  const tax = discountedSubtotal * (vatRate / 100)

  return discountedSubtotal + tax
})

// Submit
async function handleSubmit() {
  if (!form.description || form.unit_price <= 0) {
    toast.add({
      title: t('common.error'),
      description: t('invoice.errors.itemRequired'),
      color: 'error'
    })
    return
  }

  isSubmitting.value = true

  try {
    if (isEditing.value && props.editItem) {
      // Update existing item
      await updateItem(props.invoiceId, props.editItem.id, {
        description: form.description,
        unit_price: form.unit_price,
        quantity: form.quantity || 1,
        vat_type_id: form.vat_type_id || undefined,
        discount_type: form.discount_type || undefined,
        discount_value: form.discount_value || undefined
      })

      toast.add({
        title: t('common.success'),
        description: t('invoice.messages.itemUpdated'),
        color: 'success'
      })
    } else {
      // Add new item
      await addItem(props.invoiceId, {
        description: form.description,
        catalog_item_id: form.catalog_item_id || undefined,
        unit_price: form.unit_price,
        quantity: form.quantity || 1,
        vat_type_id: form.vat_type_id || undefined,
        tooth_number: form.tooth_number || undefined,
        surfaces: form.surfaces?.length ? form.surfaces : undefined,
        discount_type: form.discount_type || undefined,
        discount_value: form.discount_value || undefined
      })

      toast.add({
        title: t('common.success'),
        description: t('invoice.messages.itemAdded'),
        color: 'success'
      })
    }

    emit('saved')
    open.value = false
    resetForm()
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, isEditing.value ? t('invoice.errors.update') : t('invoice.errors.create')),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

function close() {
  open.value = false
  resetForm()
}

function resetForm() {
  selectedItem.value = null
  form.description = ''
  form.catalog_item_id = undefined
  form.unit_price = 0
  form.quantity = 1
  form.vat_type_id = vatTypes.value.find(v => v.is_default)?.id
  form.tooth_number = undefined
  form.surfaces = []
  form.discount_type = undefined
  form.discount_value = undefined
}

function populateFromEditItem() {
  if (!props.editItem) return

  const item = props.editItem
  form.description = item.description
  form.catalog_item_id = item.catalog_item_id
  form.unit_price = item.unit_price
  form.quantity = item.quantity
  form.vat_type_id = item.vat_type_id
  form.tooth_number = item.tooth_number
  form.surfaces = item.surfaces || []
  form.discount_type = item.discount_type
  form.discount_value = item.discount_value

  // Set selected item to show the treatment card
  if (item.catalog_item) {
    selectedItem.value = {
      id: item.catalog_item.id,
      internal_code: item.catalog_item.internal_code,
      names: item.catalog_item.names,
      default_price: item.catalog_item.default_price
    } as TreatmentCatalogItem
  } else {
    selectedItem.value = null
  }
}

// Reset/populate form and load VAT types when modal opens
watch(open, async (isOpen) => {
  if (isOpen) {
    await loadVatTypes()
    if (props.editItem) {
      populateFromEditItem()
    } else {
      resetForm()
    }
  }
})
</script>

<template>
  <UModal v-model:open="open">
    <template #content>
      <UCard class="w-full max-w-lg">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ isEditing ? t('invoice.editItem') : t('invoice.addItem') }}
            </h2>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              @click="close"
            />
          </div>
        </template>

        <div class="max-h-[60vh] overflow-y-auto pr-1">
          <form
            class="space-y-4"
            @submit.prevent="handleSubmit"
          >
            <!-- Catalog item search -->
            <UFormField
              :label="t('invoice.selectTreatment')"
              required
            >
              <TreatmentVisualSelector
                :model-value="selectedItem"
                :in-modal="true"
                @update:model-value="handleItemSelect"
              />
            </UFormField>

            <!-- Quantity and tooth number -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <UFormField :label="t('invoice.itemQuantity')">
                <UInput
                  v-model.number="form.quantity"
                  type="number"
                  min="1"
                  required
                />
              </UFormField>

              <UFormField :label="t('budget.items.toothNumber')">
                <UInput
                  v-model.number="form.tooth_number"
                  type="number"
                  min="11"
                  max="85"
                  :placeholder="t('budget.items.toothNumberPlaceholder')"
                />
              </UFormField>
            </div>

            <!-- Tooth surfaces -->
            <UFormField
              v-if="form.tooth_number"
              :label="t('budget.items.surfaces')"
            >
              <div class="flex flex-wrap gap-2">
                <UButton
                  v-for="surface in toothSurfaces"
                  :key="surface"
                  size="sm"
                  :variant="form.surfaces?.includes(surface) ? 'solid' : 'outline'"
                  :color="form.surfaces?.includes(surface) ? 'primary' : 'neutral'"
                  @click="toggleSurface(surface)"
                >
                  {{ surface }}
                </UButton>
              </div>
            </UFormField>

            <!-- Price (editable) -->
            <UFormField :label="t('invoice.itemPrice')">
              <UInput
                v-model.number="form.unit_price"
                type="number"
                min="0"
                step="0.01"
                required
              />
            </UFormField>

            <!-- VAT type -->
            <UFormField :label="t('invoice.vat')">
              <USelectMenu
                v-model="form.vat_type_id"
                :items="vatTypeOptions"
                :placeholder="t('invoice.selectVatType')"
                :loading="isLoadingVat"
                value-key="value"
              />
            </UFormField>

            <!-- Discount -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <UFormField :label="t('budget.discountType')">
                <USelectMenu
                  v-model="form.discount_type"
                  :items="[
                    { label: '-', value: '' },
                    { label: t('budget.percentage'), value: 'percentage' },
                    { label: t('budget.absolute'), value: 'absolute' }
                  ]"
                  value-key="value"
                />
              </UFormField>
              <UFormField
                v-if="form.discount_type"
                :label="t('budget.discountValue')"
              >
                <UInput
                  v-model.number="form.discount_value"
                  type="number"
                  step="0.01"
                  min="0"
                  :max="form.discount_type === 'percentage' ? 100 : undefined"
                />
              </UFormField>
            </div>

            <!-- Preview total -->
            <div
              v-if="form.unit_price > 0"
              class="flex justify-between items-center p-3 bg-surface-muted rounded-lg"
            >
              <span class="text-muted">{{ t('budget.items.lineTotal') }}</span>
              <span class="text-h1 tnum text-default">
                {{ formatPrice(previewTotal) }}
              </span>
            </div>
          </form>
        </div>

        <template #footer>
          <div class="flex justify-end gap-3">
            <UButton
              variant="outline"
              color="neutral"
              @click="close"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :icon="isEditing ? 'i-lucide-check' : 'i-lucide-plus'"
              :disabled="!form.description || form.unit_price <= 0"
              :loading="isSubmitting"
              @click="handleSubmit"
            >
              {{ isEditing ? t('common.save') : t('invoice.addItem') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
