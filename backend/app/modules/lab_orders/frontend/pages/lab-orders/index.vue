<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useLabOrders, type LabOrder, type OrderStatus } from '../../composables/useLabOrders'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const labOrdersApi = useLabOrders()

if (!can(PERMISSIONS.labOrders.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.labOrders.write))

const STATUSES: OrderStatus[] = ['sent', 'in_progress', 'ready', 'received', 'cancelled']
const statusOptions = computed(() => STATUSES.map(s => ({ value: s, label: t(`labOrders.statuses.${s}`) })))

const items = ref<LabOrder[]>([])
const loading = ref(false)
const filterStatus = ref<OrderStatus | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await labOrdersApi.list({ order_status: filterStatus.value, page: 1, page_size: 100 })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(filterStatus, load)

async function setStatus(order: LabOrder, newStatus: OrderStatus) {
  await labOrdersApi.update(order.id, { status: newStatus })
  await load()
}

async function remove(id: string) {
  await labOrdersApi.remove(id)
  await load()
}

const columns = [
  { accessorKey: 'sent_date', header: t('labOrders.sentDate') },
  { accessorKey: 'patient_name', header: t('labOrders.patient') },
  { accessorKey: 'lab_contact_name', header: t('labOrders.lab') },
  { accessorKey: 'work_type', header: t('labOrders.workType') },
  { accessorKey: 'tooth_reference', header: t('labOrders.tooth') },
  { accessorKey: 'status', header: t('labOrders.status') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('labOrders.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        to="/lab-orders/new"
      >
        {{ t('labOrders.add') }}
      </UButton>
    </div>

    <USelect
      v-model="filterStatus"
      :items="statusOptions"
      :placeholder="t('labOrders.filterByStatus')"
      class="max-w-xs"
    />

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #work_type-cell="{ row }">
        {{ t(`labOrders.workTypes.${row.original.work_type}`) }}
      </template>
      <template #status-cell="{ row }">
        <USelect
          v-if="canWrite"
          :model-value="row.original.status"
          :items="statusOptions"
          size="xs"
          @update:model-value="(v) => setStatus(row.original, v as OrderStatus)"
        />
        <span v-else>{{ t(`labOrders.statuses.${row.original.status}`) }}</span>
      </template>
      <template #actions-cell="{ row }">
        <UButton
          v-if="canWrite"
          icon="i-lucide-trash-2"
          variant="ghost"
          color="error"
          size="xs"
          @click="remove(row.original.id)"
        />
      </template>
    </UTable>
  </div>
</template>
