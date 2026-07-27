<script setup lang="ts">
import type { SupplierItem } from '../composables/useSupplierItems'

const props = defineProps<{ itemId: string, itemName: string }>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()
const supplierItemsApi = useSupplierItems()
const suppliersApi = useSuppliers()

const links = ref<SupplierItem[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await supplierItemsApi.list({ inventory_item_id: props.itemId, page_size: 100 })
    links.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)

// --- Supplier picker for the add form ---
const supplierOptions = ref<{ value: string, label: string }[]>([])
async function loadSuppliers() {
  const res = await suppliersApi.list({ page_size: 200 })
  supplierOptions.value = res.data.map(s => ({ value: s.contact_id, label: s.name }))
}
onMounted(loadSuppliers)

// --- Add link form ---
const saving = ref(false)
const form = ref({
  supplier_contact_id: '',
  supplier_sku: '',
  unit_price: 0,
  is_preferred_supplier: false,
  notes: ''
})

function resetForm() {
  form.value = { supplier_contact_id: '', supplier_sku: '', unit_price: 0, is_preferred_supplier: false, notes: '' }
}

async function submit() {
  if (!form.value.supplier_contact_id) return
  saving.value = true
  try {
    await supplierItemsApi.create({
      supplier_contact_id: form.value.supplier_contact_id,
      inventory_item_id: props.itemId,
      supplier_sku: form.value.supplier_sku || null,
      unit_price: form.value.unit_price,
      is_preferred_supplier: form.value.is_preferred_supplier,
      notes: form.value.notes || null
    })
    resetForm()
    await load()
  } finally {
    saving.value = false
  }
}

async function remove(id: string) {
  await supplierItemsApi.remove(id)
  await load()
}

async function togglePreferred(link: SupplierItem) {
  await supplierItemsApi.update(link.id, { is_preferred_supplier: !link.is_preferred_supplier })
  await load()
}
</script>

<template>
  <UModal :open="true" @update:open="(v) => !v && emit('close')">
    <template #content>
      <div class="p-4 space-y-4 max-w-xl">
        <h2 class="text-h3 text-default">
          {{ t('inventory.suppliers.title') }} — {{ itemName }}
        </h2>

        <div v-if="loading" class="text-caption text-subtle">
          {{ t('common.loading') }}
        </div>

        <table v-else class="w-full text-body-sm">
          <thead>
            <tr class="text-left text-caption text-subtle">
              <th>{{ t('inventory.suppliers.supplier') }}</th>
              <th>{{ t('inventory.suppliers.sku') }}</th>
              <th>{{ t('inventory.suppliers.price') }}</th>
              <th>{{ t('inventory.suppliers.leadTime') }}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="link in links" :key="link.id">
              <td>
                <button class="flex items-center gap-1" @click="togglePreferred(link)">
                  <UIcon
                    :name="link.is_preferred_supplier ? 'i-lucide-star' : 'i-lucide-star-off'"
                    :class="link.is_preferred_supplier ? 'text-warning' : 'text-subtle'"
                  />
                  {{ link.supplier_name }}
                </button>
              </td>
              <td>{{ link.supplier_sku ?? '—' }}</td>
              <td class="tnum">{{ link.unit_price }}</td>
              <td>{{ link.lead_time_days != null ? `${link.lead_time_days}d` : '—' }}</td>
              <td>
                <UButton icon="i-lucide-trash-2" variant="ghost" color="error" size="xs" @click="remove(link.id)" />
              </td>
            </tr>
            <tr v-if="!links.length">
              <td colspan="5" class="text-caption text-subtle py-2">
                {{ t('inventory.suppliers.empty') }}
              </td>
            </tr>
          </tbody>
        </table>

        <div class="space-y-2 p-3 rounded-lg border border-default">
          <div class="text-caption font-medium">
            {{ t('inventory.suppliers.add') }}
          </div>
          <div class="flex flex-wrap gap-2">
            <USelect
              v-model="form.supplier_contact_id"
              :items="supplierOptions"
              :placeholder="t('inventory.suppliers.pickSupplier')"
              class="min-w-40"
            />
            <UInput v-model="form.supplier_sku" :placeholder="t('inventory.suppliers.sku')" class="w-28" />
            <UInput v-model.number="form.unit_price" type="number" step="0.01" :placeholder="t('inventory.suppliers.price')" class="w-28" />
            <UCheckbox v-model="form.is_preferred_supplier" :label="t('inventory.suppliers.preferred')" />
            <UButton :loading="saving" :disabled="!form.supplier_contact_id" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>

        <div class="flex justify-end">
          <UButton variant="ghost" @click="emit('close')">
            {{ t('actions.close') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
