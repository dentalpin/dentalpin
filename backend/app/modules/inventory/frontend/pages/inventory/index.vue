<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useInventory,
  type InventoryItem,
  type InventoryCategory,
  type InventoryItemCreatePayload,
} from '../../composables/useInventory'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const inventoryApi = useInventory()

if (!can(PERMISSIONS.inventory.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.inventory.write))
const canDelete = computed(() => can(PERMISSIONS.inventory.delete))

// --- Data ---
const items = ref<InventoryItem[]>([])
const total = ref(0)
const loading = ref(false)
const categories = ref<InventoryCategory[]>([])
const lowStockItems = ref<{ item_id: string, code: string, name: string, quantity: number, min_quantity: number, unit: string }[]>([])
const stats = ref<Record<string, number>>({})

// --- Filters ---
const search = ref('')
const filterCategory = ref<string | undefined>(undefined)
const filterLowStock = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)

async function load() {
  loading.value = true
  try {
    const res = await inventoryApi.listItems({
      search: search.value || undefined,
      category_id: filterCategory.value,
      low_stock: filterLowStock.value || undefined,
      page: currentPage.value,
      page_size: pageSize.value,
    })
    items.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function loadCategories() {
  const res = await inventoryApi.listCategories()
  categories.value = res.data
}

async function loadLowStock() {
  const res = await inventoryApi.lowStock()
  lowStockItems.value = res.data
}

async function loadDashboard() {
  const res = await inventoryApi.dashboard()
  stats.value = res.data
}

onMounted(async () => {
  await Promise.all([load(), loadCategories(), loadLowStock(), loadDashboard()])
})

watch([search, filterCategory, filterLowStock], () => {
  currentPage.value = 1
  load()
})

// --- Add/Edit modal ---
const showModal = ref(false)
const editingItem = ref<InventoryItem | null>(null)
const saving = ref(false)
const form = ref<InventoryItemCreatePayload>({
  code: '',
  name: '',
  category_id: null,
  quantity: 0,
  min_quantity: 0,
  unit: 'units',
  location: '',
  supplier: '',
  description: '',
})

function openAdd() {
  editingItem.value = null
  form.value = {
    code: '',
    name: '',
    category_id: null,
    quantity: 0,
    min_quantity: 0,
    unit: 'units',
    location: '',
    supplier: '',
    description: '',
  }
  showModal.value = true
}

function openEdit(item: InventoryItem) {
  editingItem.value = item
  form.value = {
    code: item.code,
    name: item.name,
    category_id: item.category_id,
    quantity: item.quantity,
    min_quantity: item.min_quantity,
    unit: item.unit,
    location: item.location || '',
    supplier: item.supplier || '',
    description: item.description || '',
  }
  showModal.value = true
}

async function submit() {
  saving.value = true
  try {
    if (editingItem.value) {
      await inventoryApi.updateItem(editingItem.value.id, {
        code: form.value.code,
        name: form.value.name,
        category_id: form.value.category_id,
        min_quantity: form.value.min_quantity,
        unit: form.value.unit,
        location: form.value.location || null,
        supplier: form.value.supplier || null,
        description: form.value.description || null,
      })
    } else {
      await inventoryApi.createItem(form.value)
    }
    showModal.value = false
    await Promise.all([load(), loadLowStock(), loadDashboard()])
  } finally {
    saving.value = false
  }
}

// --- Stock adjustment modal ---
const showAdjustModal = ref(false)
const adjustItem = ref<InventoryItem | null>(null)
const adjustDelta = ref(0)
const adjustReason = ref('')
const adjusting = ref(false)

function openAdjust(item: InventoryItem) {
  adjustItem.value = item
  adjustDelta.value = 0
  adjustReason.value = ''
  showAdjustModal.value = true
}

async function submitAdjust() {
  if (!adjustItem.value || adjustDelta.value === 0) return
  adjusting.value = true
  try {
    const res = await inventoryApi.adjustStock(adjustItem.value.id, {
      delta: adjustDelta.value,
      reason: adjustReason.value || undefined,
    })
    if (res.data) {
      // Update the item in the list
      const idx = items.value.findIndex(i => i.id === adjustItem.value!.id)
      if (idx >= 0) items.value[idx] = res.data
    }
    showAdjustModal.value = false
    await Promise.all([loadLowStock(), loadDashboard()])
  } finally {
    adjusting.value = false
  }
}

// --- Delete ---
async function removeItem(id: string) {
  if (!confirm(t('inventory.confirmDelete'))) return
  await inventoryApi.deleteItem(id)
  await Promise.all([load(), loadLowStock(), loadDashboard()])
}

// --- Table columns ---
const columns = [
  { accessorKey: 'code', header: t('inventory.code') },
  { accessorKey: 'name', header: t('inventory.name') },
  { accessorKey: 'quantity', header: t('inventory.quantity') },
  { accessorKey: 'min_quantity', header: t('inventory.minQuantity') },
  { accessorKey: 'unit', header: t('inventory.unit') },
  { accessorKey: 'location', header: t('inventory.location') },
  { accessorKey: 'supplier', header: t('inventory.supplier') },
  { accessorKey: 'actions', header: '' },
]
</script>

<template>
  <div class="p-4 space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('inventory.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openAdd"
      >
        {{ t('inventory.addItem') }}
      </UButton>
    </div>

    <!-- Dashboard stats -->
    <div class="flex flex-wrap gap-3">
      <UCard class="flex-1 min-w-[140px]">
        <div class="text-sm text-muted">{{ t('inventory.totalItems') }}</div>
        <div class="text-xl font-bold">{{ stats.total_items ?? 0 }}</div>
      </UCard>
      <UCard class="flex-1 min-w-[140px]">
        <div class="text-sm text-muted">{{ t('inventory.lowStockCount') }}</div>
        <div class="text-xl font-bold text-orange-500">{{ stats.low_stock_count ?? 0 }}</div>
      </UCard>
      <UCard class="flex-1 min-w-[140px]">
        <div class="text-sm text-muted">{{ t('inventory.outOfStockCount') }}</div>
        <div class="text-xl font-bold text-red-500">{{ stats.out_of_stock_count ?? 0 }}</div>
      </UCard>
      <UCard class="flex-1 min-w-[140px]">
        <div class="text-sm text-muted">{{ t('inventory.totalQuantity') }}</div>
        <div class="text-xl font-bold">{{ stats.total_quantity ?? 0 }}</div>
      </UCard>
    </div>

    <!-- Low-stock alerts -->
    <UCard v-if="lowStockItems.length > 0">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-alert-triangle" class="text-orange-500" />
          <span class="font-semibold">{{ t('inventory.lowStockAlerts') }}</span>
          <UBadge color="warning" size="sm">{{ lowStockItems.length }}</UBadge>
        </div>
      </template>
      <div class="flex flex-wrap gap-2">
        <UBadge
          v-for="item in lowStockItems"
          :key="item.item_id"
          color="warning"
          variant="soft"
        >
          {{ item.name }}: {{ item.quantity }}/{{ item.min_quantity }} {{ item.unit }}
        </UBadge>
      </div>
    </UCard>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 items-end">
      <UInput
        v-model="search"
        :placeholder="t('inventory.search')"
        icon="i-lucide-search"
        class="max-w-xs"
      />
      <USelect
        v-model="filterCategory"
        :items="categories.map(c => ({ value: c.id, label: c.name }))"
        :placeholder="t('inventory.filterByCategory')"
        class="max-w-xs"
      />
      <UCheckbox
        v-model="filterLowStock"
        :label="t('inventory.lowStockOnly')"
      />
    </div>

    <!-- Items table -->
    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #quantity-cell="{ row }">
        <UBadge
          :color="row.original.is_low_stock ? 'warning' : 'success'"
          variant="soft"
        >
          {{ row.original.quantity }} {{ row.original.unit }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex gap-1">
          <UButton
            v-if="canWrite"
            icon="i-lucide-arrow-up-down"
            variant="ghost"
            size="xs"
            :title="t('inventory.adjustStock')"
            @click="openAdjust(row.original)"
          />
          <UButton
            v-if="canWrite"
            icon="i-lucide-pencil"
            variant="ghost"
            size="xs"
            @click="openEdit(row.original)"
          />
          <UButton
            v-if="canDelete"
            icon="i-lucide-trash-2"
            variant="ghost"
            color="error"
            size="xs"
            @click="removeItem(row.original.id)"
          />
        </div>
      </template>
    </UTable>

    <!-- Pagination -->
    <div v-if="total > pageSize" class="flex justify-center gap-2">
      <UButton
        :disabled="currentPage <= 1"
        variant="outline"
        size="sm"
        @click="currentPage--; load()"
      >
        {{ t('inventory.prev') }}
      </UButton>
      <span class="text-sm text-muted self-center">
        {{ currentPage }} / {{ Math.ceil(total / pageSize) }}
      </span>
      <UButton
        :disabled="currentPage * pageSize >= total"
        variant="outline"
        size="sm"
        @click="currentPage++; load()"
      >
        {{ t('inventory.next') }}
      </UButton>
    </div>

    <!-- Add/Edit modal -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ editingItem ? t('inventory.editItem') : t('inventory.addItem') }}
          </h2>
          <UInput v-model="form.code" :placeholder="t('inventory.code')" required />
          <UInput v-model="form.name" :placeholder="t('inventory.name')" required />
          <USelect
            v-model="form.category_id"
            :items="[
              { value: null, label: t('inventory.noCategory') },
              ...categories.map(c => ({ value: c.id, label: c.name })),
            ]"
            :placeholder="t('inventory.category')"
          />
          <div v-if="!editingItem" class="flex gap-2">
            <UInput v-model.number="form.quantity" type="number" :placeholder="t('inventory.quantity')" class="flex-1" />
            <UInput v-model.number="form.min_quantity" type="number" :placeholder="t('inventory.minQuantity')" class="flex-1" />
          </div>
          <div class="flex gap-2">
            <UInput v-model="form.unit" :placeholder="t('inventory.unit')" class="flex-1" />
            <UInput v-model="form.location" :placeholder="t('inventory.location')" class="flex-1" />
          </div>
          <UInput v-model="form.supplier" :placeholder="t('inventory.supplier')" />
          <UInput v-model="form.description" :placeholder="t('inventory.description')" />
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

    <!-- Stock adjustment modal -->
    <UModal v-model:open="showAdjustModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('inventory.adjustStock') }}
          </h2>
          <p v-if="adjustItem" class="text-sm text-muted">
            {{ adjustItem.name }} ({{ adjustItem.code }}) — {{ t('inventory.currentStock') }}: {{ adjustItem.quantity }} {{ adjustItem.unit }}
          </p>
          <UInput
            v-model.number="adjustDelta"
            type="number"
            :placeholder="t('inventory.deltaPlaceholder')"
          />
          <p class="text-xs text-muted">
            {{ t('inventory.deltaHelp') }}
          </p>
          <UInput v-model="adjustReason" :placeholder="t('inventory.reason')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showAdjustModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="adjusting" :disabled="adjustDelta === 0" @click="submitAdjust">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
