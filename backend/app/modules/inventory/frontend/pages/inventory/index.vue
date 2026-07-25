<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useInventory, type InventoryCategory, type InventoryItem } from '../../composables/useInventory'
import InventoryMovementsModal from '../../components/InventoryMovementsModal.vue'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const inventoryApi = useInventory()

if (!can(PERMISSIONS.inventory.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.inventory.write))

const CATEGORIES: InventoryCategory[] = ['consumables', 'ppe', 'materials', 'medication', 'other']
const categoryOptions = computed(() => CATEGORIES.map(c => ({ value: c, label: t(`inventory.categories.${c}`) })))

const items = ref<InventoryItem[]>([])
const loading = ref(false)
const filterCategory = ref<InventoryCategory | undefined>(undefined)
const lowStockOnly = ref(false)
const search = ref('')

async function load() {
  loading.value = true
  try {
    const res = await inventoryApi.list({
      category: filterCategory.value,
      search: search.value,
      low_stock_only: lowStockOnly.value,
      page: 1,
      page_size: 1000
    })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([filterCategory, lowStockOnly, search], load)

async function bump(item: InventoryItem, delta: number) {
  await inventoryApi.adjust(item.id, delta)
  await load()
}

// --- Add item modal ---
const showModal = ref(false)
const saving = ref(false)
const form = ref({
  name: '',
  category: 'consumables' as InventoryCategory,
  unit: '',
  quantity_on_hand: 0,
  low_stock_threshold: 0,
  unit_cost: null as number | null,
  notes: ''
})

function openCreate() {
  form.value = {
    name: '',
    category: 'consumables',
    unit: '',
    quantity_on_hand: 0,
    low_stock_threshold: 0,
    unit_cost: null,
    notes: ''
  }
  showModal.value = true
}

async function submit() {
  saving.value = true
  try {
    await inventoryApi.create({
      name: form.value.name,
      category: form.value.category,
      unit: form.value.unit || null,
      quantity_on_hand: form.value.quantity_on_hand,
      low_stock_threshold: form.value.low_stock_threshold,
      unit_cost: form.value.unit_cost,
      notes: form.value.notes || null
    })
    showModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

// --- Edit item modal (new in Phase 12 — mainly for unit_cost) ---
const showEditModal = ref(false)
const editSaving = ref(false)
const editingId = ref<string | null>(null)
const editForm = ref({
  name: '',
  category: 'consumables' as InventoryCategory,
  unit: '',
  low_stock_threshold: 0,
  unit_cost: null as number | null,
  notes: ''
})

function openEdit(item: InventoryItem) {
  editingId.value = item.id
  editForm.value = {
    name: item.name,
    category: item.category,
    unit: item.unit ?? '',
    low_stock_threshold: Number(item.low_stock_threshold),
    unit_cost: item.unit_cost !== null && item.unit_cost !== undefined ? Number(item.unit_cost) : null,
    notes: item.notes ?? ''
  }
  showEditModal.value = true
}

async function submitEdit() {
  if (!editingId.value) return
  editSaving.value = true
  try {
    await inventoryApi.update(editingId.value, {
      name: editForm.value.name,
      category: editForm.value.category,
      unit: editForm.value.unit || null,
      low_stock_threshold: editForm.value.low_stock_threshold,
      unit_cost: editForm.value.unit_cost,
      notes: editForm.value.notes || null
    })
    showEditModal.value = false
    await load()
  } finally {
    editSaving.value = false
  }
}

// --- Movement history modal ---
const historyItem = ref<InventoryItem | null>(null)

async function remove(id: string) {
  await inventoryApi.remove(id)
  await load()
}

const columns = [
  { accessorKey: 'name', header: t('inventory.name') },
  { accessorKey: 'category', header: t('inventory.category') },
  { accessorKey: 'quantity_on_hand', header: t('inventory.quantity') },
  { accessorKey: 'unit_cost', header: t('inventory.unitCost') },
  { accessorKey: 'average_cost', header: t('inventory.averageCost') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('inventory.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('inventory.add') }}
      </UButton>
    </div>

    <div class="flex flex-wrap gap-2 items-center">
      <UInput
        v-model="search"
        icon="i-lucide-search"
        :placeholder="t('inventory.search')"
        class="max-w-xs"
      />
      <USelect
        v-model="filterCategory"
        :items="categoryOptions"
        :placeholder="t('inventory.filterByCategory')"
        class="max-w-xs"
      />
      <UButton
        :variant="lowStockOnly ? 'solid' : 'outline'"
        color="warning"
        icon="i-lucide-triangle-alert"
        size="sm"
        @click="lowStockOnly = !lowStockOnly"
      >
        {{ t('inventory.lowStockOnly') }}
      </UButton>
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #category-cell="{ row }">
        {{ t(`inventory.categories.${row.original.category}`) }}
      </template>
      <template #quantity_on_hand-cell="{ row }">
        <div class="flex items-center gap-2">
          <UBadge v-if="row.original.is_low_stock" color="warning" variant="soft">
            {{ t('inventory.lowStock') }}
          </UBadge>
          <span>{{ row.original.quantity_on_hand }}{{ row.original.unit ? ` ${row.original.unit}` : '' }}</span>
        </div>
      </template>
      <template #unit_cost-cell="{ row }">
        {{ row.original.unit_cost ?? '—' }}
      </template>
      <template #average_cost-cell="{ row }">
        {{ row.original.average_cost ?? '—' }}
      </template>
      <template #actions-cell="{ row }">
        <div class="flex gap-1">
          <UButton
            icon="i-lucide-history"
            variant="ghost"
            size="xs"
            @click="historyItem = row.original"
          />
          <template v-if="canWrite">
            <UButton icon="i-lucide-minus" variant="ghost" size="xs" @click="bump(row.original, -1)" />
            <UButton icon="i-lucide-plus" variant="ghost" size="xs" @click="bump(row.original, 1)" />
            <UButton icon="i-lucide-pencil" variant="ghost" size="xs" @click="openEdit(row.original)" />
            <UButton
              icon="i-lucide-trash-2"
              variant="ghost"
              color="error"
              size="xs"
              @click="remove(row.original.id)"
            />
          </template>
        </div>
      </template>
    </UTable>

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('inventory.add') }}
          </h2>
          <UInput v-model="form.name" :placeholder="t('inventory.name')" />
          <USelect v-model="form.category" :items="categoryOptions" />
          <UInput v-model="form.unit" :placeholder="t('inventory.unit')" />
          <UInput v-model.number="form.quantity_on_hand" type="number" step="1" :placeholder="t('inventory.quantity')" />
          <UInput v-model.number="form.low_stock_threshold" type="number" step="1" :placeholder="t('inventory.lowStockThreshold')" />
          <UInput v-model.number="form.unit_cost" type="number" step="0.01" :placeholder="t('inventory.unitCost')" />
          <UInput v-model="form.notes" :placeholder="t('inventory.notes')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <UModal v-model:open="showEditModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('inventory.edit') }}
          </h2>
          <UInput v-model="editForm.name" :placeholder="t('inventory.name')" />
          <USelect v-model="editForm.category" :items="categoryOptions" />
          <UInput v-model="editForm.unit" :placeholder="t('inventory.unit')" />
          <UInput v-model.number="editForm.low_stock_threshold" type="number" step="1" :placeholder="t('inventory.lowStockThreshold')" />
          <UInput v-model.number="editForm.unit_cost" type="number" step="0.01" :placeholder="t('inventory.unitCost')" />
          <UInput v-model="editForm.notes" :placeholder="t('inventory.notes')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showEditModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="editSaving" @click="submitEdit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <InventoryMovementsModal
      v-if="historyItem"
      :item="historyItem"
      @close="historyItem = null"
      @changed="load"
    />
  </div>
</template>
