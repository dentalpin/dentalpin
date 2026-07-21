<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import type { Patient } from '~/types'
import { useLabOrders, type LabOrder, type OrderStatus, type WorkType, type ImpressionType, type Shade, VITA_CLASSICAL_SHADES } from '../../composables/useLabOrders'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const labOrdersApi = useLabOrders()
// `useContacts` comes from the `contacts` module (Phase 2). Nuxt
// auto-imports composables across all merged module layers, the same
// way `budget`'s frontend calls `useCatalog()` with no import statement
// (see BudgetItemModal.vue) — so no import is needed here either.
const contactsApi = useContacts()

if (!can(PERMISSIONS.labOrders.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.labOrders.write))

const WORK_TYPES: WorkType[] = ['crown', 'bridge', 'denture', 'implant', 'veneer', 'orthodontic', 'repair', 'other']
const workTypeOptions = computed(() => WORK_TYPES.map(w => ({ value: w, label: t(`labOrders.workTypes.${w}`) })))

const IMPRESSION_TYPES: ImpressionType[] = ['alginate', 'pvs_silicone', 'digital_scan', 'other']
const impressionTypeOptions = computed(() => IMPRESSION_TYPES.map(i => ({ value: i, label: t(`labOrders.impressionTypes.${i}`) })))

const shadeOptions = computed(() => VITA_CLASSICAL_SHADES.map(s => ({ value: s, label: s })))

const STATUSES: OrderStatus[] = ['sent', 'in_progress', 'ready', 'received', 'cancelled']
const statusOptions = computed(() => STATUSES.map(s => ({ value: s, label: t(`labOrders.statuses.${s}`) })))

const items = ref<LabOrder[]>([])
const loading = ref(false)
const filterStatus = ref<OrderStatus | undefined>(undefined)

interface LabContactOption { id: string, name: string }
const labContacts = ref<LabContactOption[]>([])
const labContactOptions = computed(() =>
  labContacts.value.map(c => ({ value: c.id, label: c.name }))
)

async function loadContacts() {
  const res = await contactsApi.list({ contact_type: 'lab', page: 1, page_size: 100 })
  labContacts.value = res.data.map((c: any) => ({ id: c.id, name: c.name }))
}

async function load() {
  loading.value = true
  try {
    const res = await labOrdersApi.list({ order_status: filterStatus.value, page: 1, page_size: 100 })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await Promise.all([load(), loadContacts()])
})
watch(filterStatus, load)

// --- Add order modal ---
const showModal = ref(false)
const saving = ref(false)
const selectedPatient = ref<Patient | null>(null)
const form = ref({
  lab_contact_id: '',
  work_type: 'crown' as WorkType,
  tooth_reference: '',
  impression_type: '' as ImpressionType | '',
  antagonist_info: '',
  shade: '',
  sent_date: new Date().toISOString().slice(0, 10),
  expected_date: '',
  notes: ''
})

function openCreate() {
  selectedPatient.value = null
  form.value = {
    lab_contact_id: labContacts.value[0]?.id ?? '',
    work_type: 'crown',
    tooth_reference: '',
    impression_type: '',
    antagonist_info: '',
    shade: '',
    sent_date: new Date().toISOString().slice(0, 10),
    expected_date: '',
    notes: ''
  }
  showModal.value = true
}

async function submit() {
  if (!selectedPatient.value || !form.value.lab_contact_id) return
  saving.value = true
  try {
    await labOrdersApi.create({
      patient_id: selectedPatient.value.id,
      lab_contact_id: form.value.lab_contact_id,
      work_type: form.value.work_type,
      tooth_reference: form.value.tooth_reference || null,
      impression_type: form.value.impression_type || null,
      antagonist_info: form.value.antagonist_info || null,
      shade: (form.value.shade || null) as Shade | null,
      sent_date: form.value.sent_date,
      expected_date: form.value.expected_date || null,
      notes: form.value.notes || null
    })
    showModal.value = false
    await load()
  } finally {
    saving.value = false
  }
}

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
        :disabled="labContacts.length === 0"
        @click="openCreate"
      >
        {{ t('labOrders.add') }}
      </UButton>
    </div>

    <p v-if="canWrite && labContacts.length === 0" class="text-caption text-subtle">
      {{ t('labOrders.noLabsHint') }}
    </p>

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

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('labOrders.add') }}
          </h2>
          <PatientSearch v-model="selectedPatient" :placeholder="t('labOrders.selectPatient')" />
          <USelect v-model="form.lab_contact_id" :items="labContactOptions" :placeholder="t('labOrders.selectLab')" />
          <USelect v-model="form.work_type" :items="workTypeOptions" />
          <UInput v-model="form.tooth_reference" :placeholder="t('labOrders.tooth')" />
          <USelect v-model="form.impression_type" :items="impressionTypeOptions" :placeholder="t('labOrders.impressionType')" />
          <UInput v-model="form.antagonist_info" :placeholder="t('labOrders.antagonistInfo')" />
          <USelect v-model="form.shade" :items="shadeOptions" :placeholder="t('labOrders.shade')" />
          <UInput v-model="form.sent_date" type="date" />
          <UInput v-model="form.expected_date" type="date" :placeholder="t('labOrders.expectedDate')" />
          <UInput v-model="form.notes" :placeholder="t('labOrders.notes')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" :disabled="!selectedPatient || !form.lab_contact_id" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
