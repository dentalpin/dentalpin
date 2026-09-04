<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('procurement.reorder.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('procurement.reorder.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.inventoryReorder.write)"
        icon="i-lucide-package-plus"
        :loading="generating"
        :disabled="selected.length === 0"
        @click="generate"
      >
        {{ t('procurement.reorder.generate') }}
      </UButton>
    </div>

    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-16"
      />
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      :title="t('procurement.common.loadError')"
      :actions="[{ label: t('procurement.common.retry'), onClick: fetchSuggestions }]"
    />

    <UCard v-else-if="suggestions.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.reorder.empty') }}
      </p>
    </UCard>

    <UCard v-else>
      <UTable
        v-model:row-selection="rowSelection"
        :data="suggestions"
        :columns="columns"
      />
    </UCard>

    <UModal v-model:open="showResult">
      <template #content>
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('procurement.reorder.generateOk') }}
            </h2>
          </template>
          <div class="space-y-1">
            <p
              v-for="order in created"
              :key="order.id"
              class="text-sm"
            >
              {{ order.supplier_name }} — {{ order.lines.length }} {{ t('procurement.orders.lines') }}
            </p>
          </div>
          <template #footer>
            <div class="flex justify-end">
              <UButton @click="showResult = false">
                {{ t('procurement.common.close') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import type { PurchaseOrder, ReorderSuggestion } from '../../../composables/useProcurement'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listReorderSuggestions, generateReorderOrders } = useProcurement()

const suggestions = ref<ReorderSuggestion[]>([])
const loading = ref(true)
const error = ref(false)
const generating = ref(false)
const showResult = ref(false)
const created = ref<PurchaseOrder[]>([])
const rowSelection = ref<Record<string, boolean>>({})

const selected = computed(() => {
  const rows = suggestions.value
  const ids: string[] = []
  for (const index of Object.keys(rowSelection.value)) {
    if (!rowSelection.value[index]) continue
    const row = rows[Number(index)]
    if (row) ids.push(row.inventory_item_id)
  }
  return ids
})

const columns = computed(() => [
  { accessorKey: 'item_name', header: t('procurement.reorder.item') },
  { accessorKey: 'usage_90d', header: t('procurement.reorder.usage90d') },
  { accessorKey: 'daily_usage', header: t('procurement.reorder.dailyUsage') },
  { accessorKey: 'supplier_name', header: t('procurement.reorder.supplier') },
  { accessorKey: 'lead_time_days', header: t('procurement.reorder.leadTime') },
  { accessorKey: 'stock_quantity', header: t('procurement.reorder.stock') },
  { accessorKey: 'on_order', header: t('procurement.reorder.onOrder') },
  { accessorKey: 'reorder_point', header: t('procurement.reorder.reorderPoint') },
  { accessorKey: 'suggested_quantity', header: t('procurement.reorder.suggestedQty') }
])

async function fetchSuggestions() {
  loading.value = true
  error.value = false
  try {
    const response = await listReorderSuggestions()
    suggestions.value = response.data
    rowSelection.value = {}
  } catch (e) {
    error.value = true
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function generate() {
  if (selected.value.length === 0) {
    toast.add({ title: t('procurement.reorder.generateEmpty'), color: 'warning' })
    return
  }
  generating.value = true
  try {
    const response = await generateReorderOrders(selected.value)
    created.value = response.data
    showResult.value = true
    await fetchSuggestions()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    generating.value = false
  }
}

onMounted(fetchSuggestions)
</script>
