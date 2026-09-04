<template>
  <div class="space-y-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('procurement.orders.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('procurement.orders.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.purchaseOrders.write)"
        icon="i-lucide-plus"
        @click="showCreate = true"
      >
        {{ t('procurement.orders.new') }}
      </UButton>
    </div>

    <div class="flex items-center gap-4">
      <UFormField :label="t('procurement.orders.status')">
        <USelect
          v-model="statusFilter"
          :items="statusOptions"
          class="w-48"
          @change="reload"
        />
      </UFormField>
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
      :actions="[{ label: t('procurement.common.retry'), onClick: fetchOrders }]"
    />

    <UCard v-else-if="orders.length === 0">
      <p class="text-sm text-muted-foreground">
        {{ t('procurement.common.empty') }}
      </p>
    </UCard>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="order in orders"
        :key="order.id"
      >
        <div class="flex items-center justify-between gap-4">
          <button
            class="min-w-0 text-left"
            @click="openDetail(order.id)"
          >
            <div class="flex items-center gap-2">
              <p class="font-medium truncate">
                {{ order.supplier_name }}
              </p>
              <UBadge
                :color="statusColor(order.status)"
                variant="soft"
              >
                {{ order.status }}
              </UBadge>
            </div>
            <p class="text-sm text-muted-foreground">
              {{ order.lines.length }} {{ t('procurement.orders.lines') }}
              <span v-if="order.expected_date"> · {{ order.expected_date }}</span>
            </p>
          </button>
          <div class="flex shrink-0 gap-2">
            <UButton
              variant="ghost"
              icon="i-lucide-file-text"
              :to="purchaseOrderPdfUrl(order.id, locale)"
              target="_blank"
            >
              {{ t('procurement.orders.pdf') }}
            </UButton>
            <UButton
              v-if="can(PERMISSIONS.purchaseOrders.write) && order.status !== 'received' && order.status !== 'cancelled'"
              icon="i-lucide-package-check"
              @click="openReceive(order)"
            >
              {{ t('procurement.orders.receive') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <div class="flex justify-center pt-2">
        <UPagination
          v-model:page="currentPage"
          :items-per-page="pageSize"
          :total="total"
        />
      </div>
    </div>

    <UModal v-model:open="showCreate">
      <template #content>
        <UCard>
          <template #header>
            <h2 class="font-semibold">
              {{ t('procurement.orders.new') }}
            </h2>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('procurement.orders.supplier')">
              <USelect
                v-model="createForm.supplier_id"
                :items="supplierOptions"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.orders.expectedDate')">
              <UInput
                v-model="createForm.expected_date"
                type="date"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('procurement.orders.notes')">
              <UInput
                v-model="createForm.notes"
                class="w-full"
              />
            </UFormField>
            <div
              v-for="(line, index) in createForm.lines"
              :key="index"
              class="grid grid-cols-12 gap-2"
            >
              <USelect
                v-model="line.inventory_item_id"
                :items="itemOptions"
                :placeholder="t('procurement.orders.item')"
                class="col-span-6"
              />
              <UInput
                v-model="line.quantity_ordered"
                type="number"
                min="1"
                step="1"
                :placeholder="t('procurement.orders.qtyOrdered')"
                class="col-span-3"
              />
              <UInput
                v-model="line.unit_price"
                type="number"
                min="0"
                step="0.01"
                :placeholder="t('procurement.orders.unitPrice')"
                class="col-span-3"
              />
            </div>
            <UButton
              variant="ghost"
              icon="i-lucide-plus"
              @click="createForm.lines.push({ inventory_item_id: '', quantity_ordered: '1', unit_price: '' })"
            >
              {{ t('procurement.orders.addLine') }}
            </UButton>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showCreate = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                @click="saveOrder"
              >
                {{ t('procurement.common.create') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="showDetail">
      <template #content>
        <UCard v-if="detail">
          <template #header>
            <div class="flex items-center justify-between">
              <h2 class="font-semibold">
                {{ detail.supplier_name }}
              </h2>
              <UBadge
                :color="statusColor(detail.status)"
                variant="soft"
              >
                {{ detail.status }}
              </UBadge>
            </div>
          </template>
          <div class="space-y-2">
            <div
              v-for="line in detail.lines"
              :key="line.id"
              class="flex justify-between text-sm"
            >
              <span>{{ line.item_name ?? line.inventory_item_id }}</span>
              <span>{{ line.quantity_received }} / {{ line.quantity_ordered }}</span>
            </div>
            <p
              v-if="detail.notes"
              class="text-sm text-muted-foreground"
            >
              {{ detail.notes }}
            </p>
          </div>
          <template
            v-if="can(PERMISSIONS.purchaseOrders.write)"
            #footer
          >
            <div class="flex flex-wrap justify-end gap-2">
              <UButton
                v-for="next in nextStatuses(detail.status)"
                :key="next"
                variant="outline"
                :loading="saving"
                @click="transition(detail, next)"
              >
                {{ next }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <UModal v-model:open="showReceive">
      <template #content>
        <UCard v-if="receiving">
          <template #header>
            <h2 class="font-semibold">
              {{ t('procurement.orders.receiveTitle') }}
            </h2>
          </template>
          <p class="text-sm text-muted-foreground">
            {{ t('procurement.orders.receiveHint') }}
          </p>
          <div class="mt-4 space-y-3">
            <div
              v-for="entry in receiveForm"
              :key="entry.purchase_order_line_id"
              class="grid grid-cols-12 items-center gap-2"
            >
              <span class="col-span-6 truncate text-sm">{{ entry.item_name }}</span>
              <UInput
                v-model="entry.good"
                type="number"
                min="0"
                step="1"
                :placeholder="t('procurement.orders.goodQty')"
                class="col-span-3"
              />
              <UInput
                v-model="entry.rejected"
                type="number"
                min="0"
                step="1"
                :placeholder="t('procurement.orders.rejectedQty')"
                class="col-span-3"
              />
            </div>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showReceive = false"
              >
                {{ t('procurement.common.cancel') }}
              </UButton>
              <UButton
                :loading="saving"
                @click="submitReceive"
              >
                {{ t('procurement.orders.receive') }}
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
import type { PurchaseOrder, PurchaseOrderStatus } from '../../../composables/useProcurement'

const { t, locale } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const {
  listPurchaseOrders,
  getPurchaseOrder,
  createPurchaseOrder,
  transitionPurchaseOrder,
  receivePurchaseOrder,
  purchaseOrderPdfUrl,
  listSuppliers,
  listInventoryItems
} = useProcurement()

const orders = ref<PurchaseOrder[]>([])
const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const statusFilter = ref<string>('all')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showCreate = ref(false)
const showDetail = ref(false)
const showReceive = ref(false)
const detail = ref<PurchaseOrder | null>(null)
const receiving = ref<PurchaseOrder | null>(null)
const supplierOptions = ref<{ label: string, value: string }[]>([])
const itemOptions = ref<{ label: string, value: string }[]>([])
const createForm = ref({
  supplier_id: '',
  expected_date: '',
  notes: '',
  lines: [{ inventory_item_id: '', quantity_ordered: '1', unit_price: '' }]
})
const receiveForm = ref<{ purchase_order_line_id: string, item_name: string, good: string, rejected: string }[]>([])

const STATUSES: PurchaseOrderStatus[] = ['draft', 'sent', 'confirmed', 'received', 'cancelled']
const statusOptions = computed(() => [
  { label: t('procurement.orders.allStatuses'), value: 'all' },
  ...STATUSES.map(s => ({ label: s, value: s }))
])

function statusColor(status: string): 'primary' | 'success' | 'warning' | 'error' | 'neutral' {
  if (status === 'received') return 'success'
  if (status === 'cancelled') return 'error'
  if (status === 'confirmed' || status === 'sent') return 'warning'
  return 'neutral'
}

function nextStatuses(status: string): string[] {
  if (status === 'draft') return ['sent', 'cancelled']
  if (status === 'sent') return ['draft', 'confirmed', 'cancelled']
  if (status === 'confirmed') return ['cancelled']
  return []
}

async function reload() {
  currentPage.value = 1
  await fetchOrders()
}

async function fetchOrders() {
  loading.value = true
  error.value = false
  try {
    const response = await listPurchaseOrders({
      order_status: statusFilter.value === 'all' ? undefined : statusFilter.value,
      page: currentPage.value,
      page_size: pageSize
    })
    orders.value = response.data
    total.value = response.total
  } catch (e) {
    error.value = true
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [suppliers, items] = await Promise.all([
    listSuppliers({ page: 1, page_size: 100 }),
    listInventoryItems({ page: 1, page_size: 100 })
  ])
  supplierOptions.value = suppliers.data.map(s => ({ label: s.name, value: s.id }))
  itemOptions.value = items.data.map(i => ({ label: i.name, value: i.id }))
}

async function saveOrder() {
  const lines = createForm.value.lines.filter(l => l.inventory_item_id && Number(l.quantity_ordered) > 0)
  if (lines.length === 0) {
    toast.add({ title: t('procurement.orders.noLines'), color: 'warning' })
    return
  }
  saving.value = true
  try {
    await createPurchaseOrder({
      supplier_id: createForm.value.supplier_id,
      expected_date: createForm.value.expected_date || null,
      notes: createForm.value.notes || null,
      lines: lines.map(l => ({
        inventory_item_id: l.inventory_item_id,
        quantity_ordered: l.quantity_ordered,
        unit_price: l.unit_price || null
      }))
    })
    toast.add({ title: t('procurement.orders.created'), color: 'success' })
    showCreate.value = false
    createForm.value = {
      supplier_id: '',
      expected_date: '',
      notes: '',
      lines: [{ inventory_item_id: '', quantity_ordered: '1', unit_price: '' }]
    }
    await fetchOrders()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function openDetail(id: string) {
  try {
    const response = await getPurchaseOrder(id)
    detail.value = response.data
    showDetail.value = true
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  }
}

async function transition(order: PurchaseOrder, next: string) {
  saving.value = true
  try {
    const response = await transitionPurchaseOrder(order.id, next)
    detail.value = response.data
    toast.add({ title: t('procurement.orders.statusChanged'), color: 'success' })
    await fetchOrders()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

function openReceive(order: PurchaseOrder) {
  receiving.value = order
  receiveForm.value = order.lines.map(l => ({
    purchase_order_line_id: l.id,
    item_name: l.item_name ?? l.inventory_item_id,
    good: '',
    rejected: ''
  }))
  showReceive.value = true
}

async function submitReceive() {
  if (!receiving.value) return
  const lines = receiveForm.value
    .flatMap(entry => [
      { purchase_order_line_id: entry.purchase_order_line_id, quantity_received: entry.good, quality: 'good' as const },
      { purchase_order_line_id: entry.purchase_order_line_id, quantity_received: entry.rejected, quality: 'rejected' as const }
    ])
    .filter(l => Number(l.quantity_received) > 0)
  if (lines.length === 0) return
  saving.value = true
  try {
    await receivePurchaseOrder(receiving.value.id, lines)
    toast.add({ title: t('procurement.orders.receivedOk'), color: 'success' })
    showReceive.value = false
    await fetchOrders()
  } catch (e) {
    toast.add({ title: t('procurement.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

watch(currentPage, fetchOrders)
onMounted(async () => {
  await Promise.all([fetchOrders(), loadOptions().catch(() => undefined)])
})
</script>
