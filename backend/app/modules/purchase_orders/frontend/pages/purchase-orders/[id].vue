<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import type { PurchaseOrder, PurchaseOrderReceipt } from '../../composables/usePurchaseOrders'
import { useSuppliers } from '../../../../suppliers/frontend/composables/useSuppliers'
import { useSupplierItems } from '../../../../supplier_items/frontend/composables/useSupplierItems'
import { useInventory } from '../../../../inventory/frontend/composables/useInventory'
import ReceiveDeliveryModal from '../../components/ReceiveDeliveryModal.vue'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const router = useRouter()
const poApi = usePurchaseOrders()
const suppliersApi = useSuppliers()
const supplierItemsApi = useSupplierItems()
const inventoryApi = useInventory()

if (!can(PERMISSIONS.purchaseOrders?.read ?? 'purchase_orders.read')) {
  await navigateTo('/')
}
const canWrite = computed(() => can(PERMISSIONS.purchaseOrders?.write ?? 'purchase_orders.write'))

const poId = route.params.id as string
const po = ref<PurchaseOrder | null>(null)
const supplierName = ref('')
const loading = ref(false)
const receipts = ref<PurchaseOrderReceipt[]>([])

async function load() {
  loading.value = true
  try {
    const res = await poApi.get(poId)
    po.value = res.data
    const supplierRes = await suppliersApi.getSupplier(po.value.supplier_contact_id)
    supplierName.value = supplierRes.data.name
    const receiptsRes = await poApi.listReceipts(poId)
    receipts.value = receiptsRes.data
  } finally {
    loading.value = false
  }
}
onMounted(load)

const canReceive = computed(() =>
  po.value && ['sent', 'confirmed', 'partially_received'].includes(po.value.status)
)
const showReceiveModal = ref(false)

const isDraft = computed(() => po.value?.status === 'draft')

// --- Header edit (draft only) ---
const savingHeader = ref(false)
async function saveHeader() {
  if (!po.value) return
  savingHeader.value = true
  try {
    await poApi.update(poId, {
      expected_delivery_date: po.value.expected_delivery_date || null,
      shipping_cost: Number(po.value.shipping_cost),
      tax_amount: Number(po.value.tax_amount),
      notes: po.value.notes || null
    })
    await load()
  } finally {
    savingHeader.value = false
  }
}

// --- Line items ---
const itemOptions = ref<{ value: string, label: string }[]>([])
async function loadItemOptions() {
  const res = await inventoryApi.list({ page_size: 500 })
  itemOptions.value = res.data.map(i => ({ value: i.id, label: i.name }))
}
onMounted(loadItemOptions)

const newItem = ref({ inventory_item_id: '', unit_price: 0, quantity_ordered: 1 })
const addingItem = ref(false)

// Autofill price from the cheapest linked supplier for this item, if any
// (13b's supplier_items) — purely a convenience default, editable after.
watch(() => newItem.value.inventory_item_id, async (itemId) => {
  if (!itemId || !po.value) return
  try {
    const res = await supplierItemsApi.list({ inventory_item_id: itemId, page_size: 1 })
    const match = res.data.find(l => l.supplier_contact_id === po.value!.supplier_contact_id)
    if (match) newItem.value.unit_price = Number(match.unit_price)
  } catch {
    // No links for this item yet — leave price at whatever it was.
  }
})

async function addItem() {
  if (!newItem.value.inventory_item_id) return
  addingItem.value = true
  try {
    const res = await poApi.addItem(poId, {
      inventory_item_id: newItem.value.inventory_item_id,
      unit_price: newItem.value.unit_price,
      quantity_ordered: newItem.value.quantity_ordered
    })
    po.value = res.data
    newItem.value = { inventory_item_id: '', unit_price: 0, quantity_ordered: 1 }
  } finally {
    addingItem.value = false
  }
}

async function removeItem(itemId: string) {
  if (!po.value) return
  const res = await poApi.removeItem(poId, itemId)
  po.value = res.data
}

// --- Lifecycle actions ---
const acting = ref(false)
async function doSend(sendEmail: boolean) {
  acting.value = true
  try {
    const res = await poApi.send(poId, sendEmail)
    po.value = res.data
  } finally {
    acting.value = false
  }
}
async function doConfirm() {
  acting.value = true
  try {
    const res = await poApi.confirm(poId)
    po.value = res.data
  } finally {
    acting.value = false
  }
}

const showCancelModal = ref(false)
const cancelReason = ref('')
async function doCancel() {
  if (!cancelReason.value.trim()) return
  acting.value = true
  try {
    const res = await poApi.cancel(poId, cancelReason.value)
    po.value = res.data
    showCancelModal.value = false
  } finally {
    acting.value = false
  }
}

async function doDelete() {
  await poApi.remove(poId)
  await router.push('/purchase-orders')
}

const downloadingPdf = ref(false)
async function viewPdf() {
  downloadingPdf.value = true
  try {
    await poApi.openPdf(poId)
  } finally {
    downloadingPdf.value = false
  }
}
</script>

<template>
  <div v-if="po" class="p-4 space-y-4 max-w-3xl">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-h2 text-default">
          {{ po.po_number }}
        </h1>
        <div class="text-caption text-subtle">
          {{ supplierName }}
        </div>
      </div>
      <div class="flex gap-2">
        <UButton icon="i-lucide-file-text" variant="outline" :loading="downloadingPdf" @click="viewPdf">
          {{ t('purchaseOrders.viewPdf') }}
        </UButton>
        <template v-if="canWrite">
          <UButton v-if="po.status === 'draft'" icon="i-lucide-send" @click="doSend(true)">
            {{ t('purchaseOrders.send') }}
          </UButton>
          <UButton v-if="po.status === 'draft'" icon="i-lucide-check" variant="outline" @click="doSend(false)">
            {{ t('purchaseOrders.markSentNoEmail') }}
          </UButton>
          <UButton v-if="po.status === 'sent'" icon="i-lucide-badge-check" @click="doConfirm">
            {{ t('purchaseOrders.confirm') }}
          </UButton>
          <UButton v-if="canReceive" icon="i-lucide-package-check" @click="showReceiveModal = true">
            {{ t('purchaseOrders.receiving.button') }}
          </UButton>
          <UButton
            v-if="['draft', 'sent', 'confirmed'].includes(po.status)"
            icon="i-lucide-x"
            color="error"
            variant="outline"
            @click="showCancelModal = true"
          >
            {{ t('purchaseOrders.cancel') }}
          </UButton>
          <UButton v-if="po.status === 'draft'" icon="i-lucide-trash-2" color="error" variant="ghost" @click="doDelete">
            {{ t('actions.delete') }}
          </UButton>
        </template>
      </div>
    </div>

    <div v-if="po.status === 'cancelled'" class="p-3 rounded-lg bg-error/10 text-error text-body-sm">
      {{ t('purchaseOrders.cancelledNote') }}: {{ po.cancellation_reason }}
    </div>

    <div class="grid grid-cols-2 gap-4 p-4 rounded-lg border border-default">
      <UInput
        v-model="po.expected_delivery_date"
        type="date"
        :disabled="!isDraft"
        :label="t('purchaseOrders.expectedDelivery')"
      />
      <UInput
        v-model.number="po.shipping_cost"
        type="number"
        step="0.01"
        :disabled="!isDraft"
        :placeholder="t('purchaseOrders.shipping')"
      />
      <UInput
        v-model.number="po.tax_amount"
        type="number"
        step="0.01"
        :disabled="!isDraft"
        :placeholder="t('purchaseOrders.tax')"
      />
      <UInput v-model="po.notes" :disabled="!isDraft" :placeholder="t('purchaseOrders.notes')" class="col-span-2" />
      <UButton v-if="isDraft && canWrite" :loading="savingHeader" class="w-fit" @click="saveHeader">
        {{ t('actions.save') }}
      </UButton>
    </div>

    <table class="w-full text-body-sm">
      <thead>
        <tr class="text-left text-caption text-subtle">
          <th>{{ t('purchaseOrders.item') }}</th>
          <th>{{ t('purchaseOrders.qty') }}</th>
          <th>{{ t('purchaseOrders.unitPrice') }}</th>
          <th>{{ t('purchaseOrders.lineTotal') }}</th>
          <th v-if="isDraft" />
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in po.items" :key="item.id">
          <td>{{ item.description }}</td>
          <td>{{ item.quantity_ordered }}</td>
          <td class="tnum">{{ item.unit_price }}</td>
          <td class="tnum">{{ item.line_total }}</td>
          <td v-if="isDraft">
            <UButton icon="i-lucide-trash-2" variant="ghost" color="error" size="xs" @click="removeItem(item.id)" />
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="isDraft && canWrite" class="flex flex-wrap gap-2 p-3 rounded-lg border border-default">
      <USelect v-model="newItem.inventory_item_id" :items="itemOptions" :placeholder="t('purchaseOrders.pickItem')" class="min-w-40" />
      <UInput v-model.number="newItem.quantity_ordered" type="number" step="1" class="w-24" />
      <UInput v-model.number="newItem.unit_price" type="number" step="0.01" class="w-28" />
      <UButton :loading="addingItem" :disabled="!newItem.inventory_item_id" @click="addItem">
        {{ t('purchaseOrders.addItem') }}
      </UButton>
    </div>

    <div class="flex justify-end">
      <table class="w-64 text-body-sm">
        <tr><td>{{ t('purchaseOrders.subtotal') }}</td><td class="tnum text-right">{{ po.subtotal }}</td></tr>
        <tr><td>{{ t('purchaseOrders.shipping') }}</td><td class="tnum text-right">{{ po.shipping_cost }}</td></tr>
        <tr><td>{{ t('purchaseOrders.tax') }}</td><td class="tnum text-right">{{ po.tax_amount }}</td></tr>
        <tr class="font-semibold border-t border-default">
          <td>{{ t('purchaseOrders.total') }}</td><td class="tnum text-right">{{ po.total }}</td>
        </tr>
      </table>
    </div>

    <div v-if="receipts.length" class="space-y-2">
      <div class="text-caption font-medium text-subtle">
        {{ t('purchaseOrders.receiving.history') }}
      </div>
      <div v-for="receipt in receipts" :key="receipt.id" class="p-3 rounded-lg border border-default text-body-sm">
        <div class="flex justify-between text-caption text-subtle mb-1">
          <span>{{ receipt.received_date }}</span>
        </div>
        <div v-for="line in receipt.lines" :key="line.id" class="flex justify-between">
          <span>{{ line.quantity_received }} — {{ t(`purchaseOrders.receiving.quality.${line.quality_status === 'wrong_item' ? 'wrongItem' : line.quality_status}`) }}</span>
        </div>
      </div>
    </div>

    <ReceiveDeliveryModal
      v-if="showReceiveModal && po"
      :po="po"
      @close="showReceiveModal = false"
      @received="load"
    />

    <UModal v-model:open="showCancelModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('purchaseOrders.cancel') }}
          </h2>
          <UInput v-model="cancelReason" :placeholder="t('purchaseOrders.cancelReason')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showCancelModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton color="error" :loading="acting" :disabled="!cancelReason.trim()" @click="doCancel">
              {{ t('purchaseOrders.confirmCancel') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
