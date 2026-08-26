<script setup lang="ts">
import type { InvoiceItemCreate, TreatmentCatalogItem, VatType } from '~~/app/types'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'added': [item: InvoiceItemCreate]
}>()

const { t, locale } = useI18n()
const api = useApi()
const { getItemName, formatPrice } = useCatalog()

// VAT types
const vatTypes = ref<VatType[]>([])
const isLoadingVat = ref(false)

// Selection state
const selectedItem = ref<TreatmentCatalogItem | null>(null)

// Item form
const form = reactive<InvoiceItemCreate>({
  description: '',
  catalog_item_id: undefined,
  internal_code: undefined,
  unit_price: 0,
  quantity: 1,
  vat_type_id: undefined,
  tooth_number: undefined,
  surfaces: [],
  discount_type: undefined,
  discount_value: undefined,
  display_order: 0
})

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
    form.internal_code = item.internal_code
    form.unit_price = item.default_price || 0
    // Set default VAT type
    const defaultVat = vatTypes.value.find(v => v.is_default)
    if (defaultVat) {
      form.vat_type_id = defaultVat.id
    }
  } else {
    form.catalog_item_id = undefined
    form.description = ''
    form.internal_code = undefined
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

// Submit - emit item to parent
function handleSubmit() {
  if (!form.catalog_item_id || !form.description) return

  emit('added', {
    description: form.description,
    catalog_item_id: form.catalog_item_id,
    internal_code: form.internal_code,
    unit_price: form.unit_price,
    quantity: form.quantity || 1,
    vat_type_id: form.vat_type_id,
    tooth_number: form.tooth_number || undefined,
    surfaces: form.surfaces?.length ? form.surfaces : undefined,
    discount_type: form.discount_type || undefined,
    discount_value: form.discount_value || undefined,
    display_order: 0
  })

  close()
}

function close() {
  resetForm()
  emit('update:open', false)
}

function resetForm() {
  selectedItem.value = null
  form.description = ''
  form.catalog_item_id = undefined
  form.internal_code = undefined
  form.unit_price = 0
  form.quantity = 1
  form.vat_type_id = vatTypes.value.find(v => v.is_default)?.id
  form.tooth_number = undefined
  form.surfaces = []
  form.discount_type = undefined
  form.discount_value = undefined
}

// Load VAT types when modal opens
watch(() => props.open, async (isOpen) => {
  if (isOpen) {
    await loadVatTypes()
    resetForm()
  }
})
</script>

<template>
  <UModal
    :open="open"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <UCard class="w-full max-w-lg">
        <template #header>
          <div class="flex items-center justify-between">
            <h2 class="text-h1 text-default">
              {{ t('invoice.addItem') }}
            </h2>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              @click="close"
            />
          </div>
        </template>

        <div class="max-h-[60vh] overflow-y-auto pr-1">
          <form
            class="space-y-4"
            @submit.prevent="handleSubmit"
          >
            <!-- Treatment selector -->
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
              icon="i-lucide-plus"
              :disabled="!form.catalog_item_id || form.unit_price <= 0"
              @click="handleSubmit"
            >
              {{ t('invoice.addItem') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
