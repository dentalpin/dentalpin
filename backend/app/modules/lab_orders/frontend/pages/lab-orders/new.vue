<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import type { Patient } from '~/types'
import { useLabOrders, type WorkType, type ImpressionType, type Shade, VITA_CLASSICAL_SHADES } from '../../composables/useLabOrders'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const labOrdersApi = useLabOrders()
const contactsApi = useContacts()

if (!can(PERMISSIONS.labOrders.write)) {
  await navigateTo('/lab-orders')
}

const WORK_TYPES: WorkType[] = ['crown', 'bridge', 'denture', 'implant', 'veneer', 'orthodontic', 'repair', 'other']
const workTypeOptions = computed(() => WORK_TYPES.map(w => ({ value: w, label: t(`labOrders.workTypes.${w}`) })))

const IMPRESSION_TYPES: ImpressionType[] = ['alginate', 'pvs_silicone', 'digital_scan', 'other']
const impressionTypeOptions = computed(() => IMPRESSION_TYPES.map(i => ({ value: i, label: t(`labOrders.impressionTypes.${i}`) })))

const shadeOptions = computed(() => VITA_CLASSICAL_SHADES.map(s => ({ value: s, label: s })))

interface LabContactOption { id: string, name: string }
const labContacts = ref<LabContactOption[]>([])
const labContactOptions = computed(() =>
  labContacts.value.map(c => ({ value: c.id, label: c.name }))
)

async function loadContacts() {
  const res = await contactsApi.list({ contact_type: 'lab', page: 1, page_size: 100 })
  labContacts.value = res.data.map((c: any) => ({ id: c.id, name: c.name }))
}

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

onMounted(async () => {
  await loadContacts()
  form.value.lab_contact_id = labContacts.value[0]?.id ?? ''
})

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
    await navigateTo('/lab-orders')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="p-4 space-y-4 max-w-lg">
    <h1 class="text-h2 text-default">
      {{ t('labOrders.add') }}
    </h1>

    <p v-if="labContacts.length === 0" class="text-caption text-subtle">
      {{ t('labOrders.noLabsHint') }}
    </p>

    <div class="space-y-4">
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
        <UButton variant="ghost" to="/lab-orders">
          {{ t('actions.cancel') }}
        </UButton>
        <UButton :loading="saving" :disabled="!selectedPatient || !form.lab_contact_id" @click="submit">
          {{ t('actions.save') }}
        </UButton>
      </div>
    </div>
  </div>
</template>
