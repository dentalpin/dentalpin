<script setup lang="ts">
import type { InventoryItem, InventoryMovement, InventoryMovementReason } from '../composables/useInventory'

const props = defineProps<{ item: InventoryItem }>()
const emit = defineEmits<{ close: [], changed: [] }>()

const { t } = useI18n()
const inventoryApi = useInventory()

const REASONS: InventoryMovementReason[] = [
  'purchase', 'return', 'donation', 'adjustment', 'damaged', 'expired', 'lost', 'used'
]
const reasonOptions = computed(() => REASONS.map(r => ({ value: r, label: t(`inventory.movements.reasons.${r}`) })))

const movements = ref<InventoryMovement[]>([])
const total = ref(0)
const loading = ref(false)
const filterReason = ref<InventoryMovementReason | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await inventoryApi.listMovements(props.item.id, {
      reason: filterReason.value,
      page: 1,
      page_size: 200
    })
    movements.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(filterReason, load)

// --- Add movement form ---
const saving = ref(false)
const form = ref({
  reason: 'purchase' as InventoryMovementReason,
  quantity_delta: 0,
  unit_cost: null as number | null,
  reference: '',
  notes: ''
})

async function submit() {
  saving.value = true
  try {
    await inventoryApi.createMovement(props.item.id, {
      reason: form.value.reason,
      quantity_delta: form.value.quantity_delta,
      unit_cost: form.value.reason === 'purchase' ? form.value.unit_cost : null,
      reference: form.value.reference || null,
      notes: form.value.notes || null
    })
    form.value = { reason: 'purchase', quantity_delta: 0, unit_cost: null, reference: '', notes: '' }
    await load()
    emit('changed')
  } finally {
    saving.value = false
  }
}

// Full-history export via the server endpoint (up to 5000 rows),
// respecting the current reason filter — not limited to the ≤200 rows
// loaded in this modal. exportCsv() returns the raw CSV text; we still
// have to build the Blob/anchor ourselves since a plain fetch response
// never triggers a browser save dialog on its own.
const exporting = ref(false)

async function exportCsv() {
  exporting.value = true
  try {
    const csvText = await inventoryApi.exportCsv(props.item.id, { reason: filterReason.value })
    const blob = new Blob([csvText], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `inventory-movements-${props.item.name}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <UModal :open="true" @update:open="(v) => !v && emit('close')">
    <template #content>
      <div class="p-4 space-y-4 max-w-2xl">
        <div class="flex items-center justify-between">
          <h2 class="text-h3 text-default">
            {{ t('inventory.movements.title') }} — {{ item.name }}
          </h2>
          <UButton icon="i-lucide-download" variant="ghost" size="xs" :loading="exporting" @click="exportCsv">
            {{ t('inventory.movements.export') }}
          </UButton>
        </div>

        <div class="grid grid-cols-2 gap-2 p-3 rounded-lg bg-elevated">
          <div>
            <div class="text-caption text-subtle">
              {{ t('inventory.unitCost') }}
            </div>
            <div class="tnum">
              {{ item.unit_cost ?? '—' }}
            </div>
          </div>
          <div>
            <div class="text-caption text-subtle">
              {{ t('inventory.averageCost') }}
            </div>
            <div class="tnum">
              {{ item.average_cost ?? '—' }}
            </div>
          </div>
        </div>

        <div class="space-y-2 p-3 rounded-lg border border-default">
          <div class="text-caption font-medium">
            {{ t('inventory.movements.add') }}
          </div>
          <div class="flex flex-wrap gap-2">
            <USelect v-model="form.reason" :items="reasonOptions" class="w-40" />
            <UInput v-model.number="form.quantity_delta" type="number" step="0.01" :placeholder="t('inventory.movements.quantityDelta')" class="w-36" />
            <UInput
              v-if="form.reason === 'purchase'"
              v-model.number="form.unit_cost"
              type="number"
              step="0.01"
              :placeholder="t('inventory.unitCost')"
              class="w-32"
            />
            <UInput v-model="form.reference" :placeholder="t('inventory.movements.reference')" class="w-32" />
            <UInput v-model="form.notes" :placeholder="t('inventory.notes')" class="flex-1 min-w-32" />
            <UButton :loading="saving" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <USelect
            v-model="filterReason"
            :items="reasonOptions"
            :placeholder="t('inventory.movements.filterByReason')"
            class="max-w-xs"
          />
          <span class="text-caption text-subtle">{{ total }} {{ t('inventory.movements.total') }}</span>
        </div>

        <UTable
          :data="movements"
          :loading="loading"
          :columns="[
            { accessorKey: 'movement_date', header: t('inventory.movements.date') },
            { accessorKey: 'reason', header: t('inventory.movements.reason') },
            { accessorKey: 'quantity_delta', header: t('inventory.movements.quantityDelta') },
            { accessorKey: 'quantity_after', header: t('inventory.movements.quantityAfter') },
            { accessorKey: 'notes', header: t('inventory.notes') }
          ]"
        >
          <template #reason-cell="{ row }">
            {{ t(`inventory.movements.reasons.${row.original.reason}`) }}
          </template>
        </UTable>

        <div class="flex justify-end">
          <UButton variant="ghost" @click="emit('close')">
            {{ t('actions.close') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
