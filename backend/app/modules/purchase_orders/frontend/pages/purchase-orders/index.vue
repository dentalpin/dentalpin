<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import type { PurchaseOrderStatus } from '../../composables/usePurchaseOrders'
import { useSuppliers } from '../../../../suppliers/frontend/composables/useSuppliers'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const poApi = usePurchaseOrders()
const suppliersApi = useSuppliers()
const router = useRouter()

if (!can(PERMISSIONS.purchaseOrders?.read ?? 'purchase_orders.read')) {
  await navigateTo('/')
}
const canWrite = computed(() => can(PERMISSIONS.purchaseOrders?.write ?? 'purchase_orders.write'))

const STATUSES: PurchaseOrderStatus[] = [
  'draft', 'sent', 'confirmed', 'partially_received', 'fully_received', 'cancelled'
]
const statusOptions = computed(() => STATUSES.map(s => ({ value: s, label: t(`purchaseOrders.statuses.${s}`) })))

const orders = ref<Awaited<ReturnType<typeof poApi.list>>['data']>([])
const loading = ref(false)
const filterStatus = ref<PurchaseOrderStatus | undefined>(undefined)
const search = ref('')

async function load() {
  loading.value = true
  try {
    const res = await poApi.list({ status: filterStatus.value, search: search.value, page: 1, page_size: 100 })
    orders.value = res.data
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch([filterStatus, search], load)

// --- Create modal ---
const showCreate = ref(false)
const creating = ref(false)
const supplierOptions = ref<{ value: string, label: string }[]>([])
const createForm = ref({ supplier_contact_id: '', expected_delivery_date: '', notes: '' })

async function openCreate() {
  const res = await suppliersApi.list({ page_size: 200 })
  supplierOptions.value = res.data.map(s => ({ value: s.contact_id, label: s.name }))
  createForm.value = { supplier_contact_id: '', expected_delivery_date: '', notes: '' }
  showCreate.value = true
}

async function submitCreate() {
  if (!createForm.value.supplier_contact_id) return
  creating.value = true
  try {
    const created = await poApi.create({
      supplier_contact_id: createForm.value.supplier_contact_id,
      expected_delivery_date: createForm.value.expected_delivery_date || null,
      notes: createForm.value.notes || null
    })
    showCreate.value = false
    await router.push(`/purchase-orders/${created.data.id}`)
  } finally {
    creating.value = false
  }
}

const columns = [
  { accessorKey: 'po_number', header: t('purchaseOrders.number') },
  { accessorKey: 'supplier_name', header: t('purchaseOrders.supplier') },
  { accessorKey: 'status', header: t('purchaseOrders.status') },
  { accessorKey: 'order_date', header: t('purchaseOrders.orderDate') },
  { accessorKey: 'total', header: t('purchaseOrders.total') }
]

const statusColor: Record<string, string> = {
  draft: 'neutral',
  sent: 'info',
  confirmed: 'primary',
  partially_received: 'warning',
  fully_received: 'success',
  cancelled: 'error'
}
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('purchaseOrders.title') }}
      </h1>
      <UButton v-if="canWrite" icon="i-lucide-plus" @click="openCreate">
        {{ t('purchaseOrders.create') }}
      </UButton>
    </div>

    <div class="flex flex-wrap gap-2">
      <UInput v-model="search" icon="i-lucide-search" :placeholder="t('purchaseOrders.search')" class="max-w-xs" />
      <USelect v-model="filterStatus" :items="statusOptions" :placeholder="t('purchaseOrders.filterByStatus')" class="max-w-xs" />
    </div>

    <UTable :data="orders" :columns="columns" :loading="loading">
      <template #po_number-cell="{ row }">
        <NuxtLink :to="`/purchase-orders/${row.original.id}`" class="text-primary font-medium">
          {{ row.original.po_number }}
        </NuxtLink>
      </template>
      <template #status-cell="{ row }">
        <UBadge :color="statusColor[row.original.status]" variant="soft">
          {{ t(`purchaseOrders.statuses.${row.original.status}`) }}
        </UBadge>
      </template>
      <template #total-cell="{ row }">
        <span class="tnum">{{ row.original.total }}</span>
      </template>
    </UTable>

    <UModal v-model:open="showCreate">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('purchaseOrders.create') }}
          </h2>
          <USelect v-model="createForm.supplier_contact_id" :items="supplierOptions" :placeholder="t('purchaseOrders.pickSupplier')" />
          <UInput v-model="createForm.expected_delivery_date" type="date" :placeholder="t('purchaseOrders.expectedDelivery')" />
          <UInput v-model="createForm.notes" :placeholder="t('purchaseOrders.notes')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showCreate = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="creating" :disabled="!createForm.supplier_contact_id" @click="submitCreate">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
