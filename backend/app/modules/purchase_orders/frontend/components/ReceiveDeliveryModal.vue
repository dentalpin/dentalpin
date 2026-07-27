<script setup lang="ts">
import type { PurchaseOrder, ReceiptLineQuality } from '../composables/usePurchaseOrders'

const props = defineProps<{ po: PurchaseOrder }>()
const emit = defineEmits<{ close: [], received: [] }>()

const { t } = useI18n()
const poApi = usePurchaseOrders()

const QUALITY_OPTIONS: { value: ReceiptLineQuality, label: string }[] = [
  { value: 'good', label: t('purchaseOrders.receiving.quality.good') },
  { value: 'damaged', label: t('purchaseOrders.receiving.quality.damaged') },
  { value: 'expired', label: t('purchaseOrders.receiving.quality.expired') },
  { value: 'wrong_item', label: t('purchaseOrders.receiving.quality.wrongItem') }
]

// One editable row per PO line item still owed quantity. Pre-filled
// with the remaining quantity (ordered - already received) so the
// common case (fully delivered, all good) is zero extra typing.
const rows = ref(
  props.po.items
    .map(item => ({
      purchase_order_item_id: item.id,
      description: item.description,
      remaining: Number(item.quantity_ordered) - Number(item.quantity_received),
      quantity_received: Math.max(0, Number(item.quantity_ordered) - Number(item.quantity_received)),
      quality_status: 'good' as ReceiptLineQuality,
      notes: ''
    }))
    .filter(r => r.remaining > 0)
)

const notes = ref('')
const saving = ref(false)

async function submit() {
  const lines = rows.value
    .filter(r => r.quantity_received > 0)
    .map(r => ({
      purchase_order_item_id: r.purchase_order_item_id,
      quantity_received: r.quantity_received,
      quality_status: r.quality_status,
      notes: r.notes || null
    }))
  if (!lines.length) return

  saving.value = true
  try {
    await poApi.recordReceipt(props.po.id, { notes: notes.value || null, lines })
    emit('received')
    emit('close')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UModal :open="true" @update:open="(v) => !v && emit('close')">
    <template #content>
      <div class="p-4 space-y-4 max-w-2xl">
        <h2 class="text-h3 text-default">
          {{ t('purchaseOrders.receiving.title') }} — {{ po.po_number }}
        </h2>

        <table class="w-full text-body-sm">
          <thead>
            <tr class="text-left text-caption text-subtle">
              <th>{{ t('purchaseOrders.item') }}</th>
              <th>{{ t('purchaseOrders.receiving.remaining') }}</th>
              <th>{{ t('purchaseOrders.receiving.receivedNow') }}</th>
              <th>{{ t('purchaseOrders.receiving.qualityLabel') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.purchase_order_item_id">
              <td>{{ row.description }}</td>
              <td class="tnum text-subtle">{{ row.remaining }}</td>
              <td>
                <UInput v-model.number="row.quantity_received" type="number" step="0.01" class="w-24" />
              </td>
              <td>
                <USelect v-model="row.quality_status" :items="QUALITY_OPTIONS" class="w-36" />
              </td>
            </tr>
            <tr v-if="!rows.length">
              <td colspan="4" class="text-caption text-subtle py-2">
                {{ t('purchaseOrders.receiving.nothingOwed') }}
              </td>
            </tr>
          </tbody>
        </table>

        <UInput v-model="notes" :placeholder="t('purchaseOrders.notes')" />

        <p class="text-caption text-subtle">
          {{ t('purchaseOrders.receiving.qualityHint') }}
        </p>

        <div class="flex justify-end gap-2">
          <UButton variant="ghost" @click="emit('close')">
            {{ t('actions.cancel') }}
          </UButton>
          <UButton :loading="saving" :disabled="!rows.some(r => r.quantity_received > 0)" @click="submit">
            {{ t('purchaseOrders.receiving.confirm') }}
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>
