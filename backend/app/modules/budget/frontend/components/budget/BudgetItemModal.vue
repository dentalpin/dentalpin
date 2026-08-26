<script setup lang="ts">
import type { BudgetItemCreate, TreatmentCatalogItem } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const props = defineProps<{
  open: boolean
  budgetId: string
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'added': []
}>()

const { t } = useI18n()
const toast = useToast()
const { formatPrice } = useCatalog()
const { addItem } = useBudgets()

// Selection state
const selectedItem = ref<TreatmentCatalogItem | null>(null)

// Item form
const form = reactive<BudgetItemCreate>({
  catalog_item_id: '',
  quantity: 1,
  tooth_number: undefined,
  surfaces: [],
  discount_type: undefined,
  discount_value: undefined,
  notes: ''
})

const isSubmitting = ref(false)

function handleItemSelect(item: TreatmentCatalogItem | null) {
  selectedItem.value = item
  form.catalog_item_id = item?.id || ''
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
  if (!selectedItem.value) return 0

  const price = selectedItem.value.default_price || 0
  const subtotal = price * (form.quantity || 1)

  if (!form.discount_type || !form.discount_value) {
    return subtotal
  }

  if (form.discount_type === 'percentage') {
    return subtotal * (1 - form.discount_value / 100)
  }

  return subtotal - form.discount_value
})

// Submit
async function handleSubmit() {
  if (!form.catalog_item_id) return

  isSubmitting.value = true

  try {
    await addItem(props.budgetId, {
      catalog_item_id: form.catalog_item_id,
      quantity: form.quantity,
      tooth_number: form.tooth_number || undefined,
      surfaces: form.surfaces?.length ? form.surfaces : undefined,
      discount_type: form.discount_type || undefined,
      discount_value: form.discount_value || undefined,
      notes: form.notes || undefined
    })

    toast.add({
      title: t('common.success'),
      description: t('budget.messages.itemAdded'),
      color: 'success'
    })

    emit('added')
    close()
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('budget.errors.create')),
      color: 'error'
    })
  } finally {
    isSubmitting.value = false
  }
}

function close() {
  resetForm()
  emit('update:open', false)
}

function resetForm() {
  selectedItem.value = null
  form.catalog_item_id = ''
  form.quantity = 1
  form.tooth_number = undefined
  form.surfaces = []
  form.discount_type = undefined
  form.discount_value = undefined
  form.notes = ''
}

// Reset form when modal opens
watch(() => props.open, (isOpen) => {
  if (isOpen) {
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
              {{ t('budget.items.add') }}
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

        <form
          class="space-y-4"
          @submit.prevent="handleSubmit"
        >
          <!-- Catalog item search -->
          <UFormField
            :label="t('budget.items.treatment')"
            required
          >
            <TreatmentVisualSelector
              :model-value="selectedItem"
              :in-modal="true"
              @update:model-value="handleItemSelect"
            />
          </UFormField>

          <!-- Quantity -->
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <UFormField :label="t('budget.items.quantity')">
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

          <!-- Notes -->
          <UFormField :label="t('budget.items.notes')">
            <UTextarea
              v-model="form.notes"
              :placeholder="t('budget.items.notesPlaceholder')"
              :rows="2"
            />
          </UFormField>

          <!-- Preview total -->
          <div
            v-if="selectedItem"
            class="flex justify-between items-center p-3 bg-surface-muted rounded-lg"
          >
            <span class="text-muted">{{ t('budget.items.lineTotal') }}</span>
            <span class="text-h1 tnum text-default">
              {{ formatPrice(previewTotal) }}
            </span>
          </div>
        </form>

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
              :disabled="!form.catalog_item_id"
              :loading="isSubmitting"
              @click="handleSubmit"
            >
              {{ t('budget.items.add') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
