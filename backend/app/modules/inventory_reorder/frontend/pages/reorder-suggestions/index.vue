<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import type { ReorderSuggestion } from '../../composables/useReorderSuggestions'
import { useSuppliers } from '../../../../suppliers/frontend/composables/useSuppliers'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const reorderApi = useReorderSuggestions()
const router = useRouter()

if (!can(PERMISSIONS.inventoryReorder?.read ?? 'inventory_reorder.read')) {
  await navigateTo('/')
}
const canWrite = computed(() => can(PERMISSIONS.inventoryReorder?.write ?? 'inventory_reorder.write'))

const suggestions = ref<ReorderSuggestion[]>([])
const loading = ref(false)
// Editable copies keyed by item id — quantity/price/supplier can be
// tweaked before generating POs, without mutating the raw suggestion.
const edits = ref<Record<string, { quantity: number, unitPrice: number, supplierContactId: string, selected: boolean }>>({})

async function load() {
  loading.value = true
  try {
    const res = await reorderApi.getSuggestions()
    suggestions.value = res.data
    edits.value = {}
    for (const s of res.data) {
      edits.value[s.inventory_item_id] = {
        quantity: Number(s.suggested_quantity),
        unitPrice: s.unit_price ? Number(s.unit_price) : 0,
        supplierContactId: s.supplier_contact_id ?? '',
        selected: !!s.supplier_contact_id // only pre-select items that already have a linked supplier
      }
    }
  } finally {
    loading.value = false
  }
}
onMounted(load)

const generating = ref(false)
async function generate() {
  const selections = suggestions.value
    .filter(s => edits.value[s.inventory_item_id]?.selected)
    .map(s => {
      const e = edits.value[s.inventory_item_id]
      return {
        inventory_item_id: s.inventory_item_id,
        supplier_contact_id: e.supplierContactId,
        quantity: e.quantity,
        unit_price: e.unitPrice
      }
    })
  if (!selections.length) return

  generating.value = true
  try {
    const res = await reorderApi.generatePOs(selections)
    const ids = res.data.purchase_order_ids
    if (ids.length === 1) {
      await router.push(`/purchase-orders/${ids[0]}`)
    } else {
      await router.push('/purchase-orders')
    }
  } finally {
    generating.value = false
  }
}
</script>

<template>
  <div class="p-4 space-y-4">
    <h1 class="text-h2 text-default">
      {{ t('reorder.title') }}
    </h1>
    <p class="text-caption text-subtle">
      {{ t('reorder.explanation') }}
    </p>

    <div v-if="loading" class="text-caption text-subtle">
      {{ t('common.loading') }}
    </div>

    <table v-else class="w-full text-body-sm">
      <thead>
        <tr class="text-left text-caption text-subtle">
          <th v-if="canWrite" />
          <th>{{ t('reorder.item') }}</th>
          <th>{{ t('reorder.onHand') }}</th>
          <th>{{ t('reorder.avgDailyUsage') }}</th>
          <th>{{ t('reorder.leadTime') }}</th>
          <th>{{ t('reorder.suggestedQty') }}</th>
          <th>{{ t('reorder.supplier') }}</th>
          <th>{{ t('reorder.unitPrice') }}</th>
          <th>{{ t('reorder.estimatedCost') }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in suggestions" :key="s.inventory_item_id">
          <td v-if="canWrite">
            <UCheckbox
              v-model="edits[s.inventory_item_id].selected"
              :disabled="!s.supplier_contact_id"
            />
          </td>
          <td>
            {{ s.item_name }}
            <UBadge v-if="s.low_confidence" color="warning" variant="soft" size="xs" class="ml-1">
              {{ t('reorder.lowConfidence') }}
            </UBadge>
          </td>
          <td class="tnum">{{ s.quantity_on_hand }}</td>
          <td class="tnum">{{ Number(s.avg_daily_usage).toFixed(2) }}</td>
          <td>{{ s.lead_time_days }}d</td>
          <td>
            <UInput
              v-if="canWrite"
              v-model.number="edits[s.inventory_item_id].quantity"
              type="number"
              step="1"
              class="w-20"
            />
            <span v-else class="tnum">{{ s.suggested_quantity }}</span>
          </td>
          <td>
            <span v-if="s.supplier_name">{{ s.supplier_name }}</span>
            <span v-else class="text-caption text-warning">{{ t('reorder.noSupplierLinked') }}</span>
          </td>
          <td>
            <UInput
              v-if="canWrite"
              v-model.number="edits[s.inventory_item_id].unitPrice"
              type="number"
              step="0.01"
              class="w-24"
            />
            <span v-else class="tnum">{{ s.unit_price ?? '—' }}</span>
          </td>
          <td class="tnum">{{ s.estimated_cost ?? '—' }}</td>
        </tr>
        <tr v-if="!suggestions.length">
          <td colspan="9" class="text-caption text-subtle py-4">
            {{ t('reorder.empty') }}
          </td>
        </tr>
      </tbody>
    </table>

    <UButton
      v-if="canWrite && suggestions.length"
      :loading="generating"
      icon="i-lucide-file-plus"
      @click="generate"
    >
      {{ t('reorder.generatePOs') }}
    </UButton>
  </div>
</template>
