<template>
  <UModal
    :open="open"
    :title="isEditing ? t('documents.editDocument') : t('documents.newDocument')"
    @update:open="$emit('update:open', $event)"
  >
    <div class="space-y-4">
      <!-- Patient selector -->
      <UFormField :label="t('documents.patient')" required>
        <USelect
          v-model="form.patient_id"
          :items="patientOptions"
          :placeholder="t('documents.selectPatient')"
        />
      </UFormField>

      <!-- Document type -->
      <UFormField :label="t('documents.type')" required>
        <USelect
          v-model="form.document_type"
          :items="documentTypeOptions"
          :placeholder="t('documents.selectType')"
          :disabled="isEditing"
        />
      </UFormField>

      <!-- Title -->
      <UFormField :label="t('documents.titleLabel')" required>
        <UInput
          v-model="form.title"
          :placeholder="t('documents.titlePlaceholder')"
        />
      </UFormField>

      <!-- Prescription content -->
      <template v-if="form.document_type === 'prescription'">
        <UFormField :label="t('documents.content.diagnosis')">
          <UInput
            v-model="form.content.diagnosis"
            :placeholder="t('documents.content.diagnosisPlaceholder')"
          />
        </UFormField>

        <div class="space-y-2">
          <div class="flex items-center justify-between">
            <label class="text-sm font-medium">{{ t('documents.content.medications') }}</label>
            <UButton
              size="sm"
              variant="ghost"
              icon="i-lucide-plus"
              @click="addMedication"
            >
              {{ t('documents.content.addMedication') }}
            </UButton>
          </div>
          <div
            v-for="(med, idx) in form.content.medications"
            :key="idx"
            class="grid grid-cols-2 gap-2 p-2 border rounded"
          >
            <UInput v-model="med.name" :placeholder="t('documents.content.medName')" />
            <UInput v-model="med.dose" :placeholder="t('documents.content.medDose')" />
            <UInput v-model="med.frequency" :placeholder="t('documents.content.medFrequency')" />
            <UInput v-model="med.duration" :placeholder="t('documents.content.medDuration')" />
          </div>
        </div>

        <UFormField :label="t('documents.content.notes')">
          <UInput
            v-model="form.content.notes"
            :placeholder="t('documents.content.notesPlaceholder')"
          />
        </UFormField>
      </template>

      <!-- Medical certificate content -->
      <template v-if="form.document_type === 'medical_certificate'">
        <UFormField :label="t('documents.content.diagnosis')">
          <UInput v-model="form.content.diagnosis" />
        </UFormField>
        <UFormField :label="t('documents.content.description')">
          <UInput v-model="form.content.description" />
        </UFormField>
        <UFormField :label="t('documents.content.recommendations')">
          <UInput v-model="form.content.recommendations" />
        </UFormField>
      </template>

      <!-- Referral content -->
      <template v-if="form.document_type === 'referral'">
        <UFormField :label="t('documents.content.referredTo')">
          <UInput v-model="form.content.referred_to" />
        </UFormField>
        <UFormField :label="t('documents.content.specialty')">
          <UInput v-model="form.content.specialty" />
        </UFormField>
        <UFormField :label="t('documents.content.reason')">
          <UInput v-model="form.content.reason" />
        </UFormField>
        <UFormField :label="t('documents.content.clinicalSummary')">
          <UInput v-model="form.content.clinical_summary" />
        </UFormField>
      </template>

      <!-- Radiology request content -->
      <template v-if="form.document_type === 'radiology_request'">
        <UFormField :label="t('documents.content.examType')">
          <UInput v-model="form.content.exam_type" />
        </UFormField>
        <UFormField :label="t('documents.content.region')">
          <UInput v-model="form.content.region" />
        </UFormField>
        <UFormField :label="t('documents.content.clinicalQuestion')">
          <UInput v-model="form.content.clinical_question" />
        </UFormField>
      </template>
    </div>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton variant="ghost" @click="$emit('update:open', false)">
          {{ t('common.cancel') }}
        </UButton>
        <UButton :loading="saving" @click="submit">
          {{ isEditing ? t('common.save') : t('common.create') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const props = defineProps<{
  open: boolean
  document?: any | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  created: []
  updated: []
}>()

const { t } = useI18n()
const api = useApi()

const isEditing = computed(() => !!props.document)
const saving = ref(false)

// Form state
const form = reactive({
  patient_id: '',
  document_type: 'prescription',
  title: '',
  content: {
    diagnosis: '',
    medications: [] as any[],
    notes: '',
    description: '',
    recommendations: '',
    referred_to: '',
    specialty: '',
    reason: '',
    clinical_summary: '',
    exam_type: '',
    region: '',
    clinical_question: ''
  }
})

// Watch for document prop changes
watch(
  () => props.document,
  (doc) => {
    if (doc) {
      form.patient_id = doc.patient_id
      form.document_type = doc.document_type
      form.title = doc.title
      form.content = { ...form.content, ...doc.content }
    } else {
      form.patient_id = ''
      form.document_type = 'prescription'
      form.title = ''
      form.content = {
        diagnosis: '',
        medications: [],
        notes: '',
        description: '',
        recommendations: '',
        referred_to: '',
        specialty: '',
        reason: '',
        clinical_summary: '',
        exam_type: '',
        region: '',
        clinical_question: ''
      }
    }
  },
  { immediate: true }
)

// Options
const patientOptions = ref<any[]>([])
const documentTypeOptions = computed(() => [
  { label: t('documents.types.prescription'), value: 'prescription' },
  { label: t('documents.types.medical_certificate'), value: 'medical_certificate' },
  { label: t('documents.types.referral'), value: 'referral' },
  { label: t('documents.types.radiology_request'), value: 'radiology_request' }
])

// Methods
function addMedication() {
  form.content.medications.push({ name: '', dose: '', frequency: '', duration: '' })
}

async function submit() {
  saving.value = true
  try {
    if (isEditing.value) {
      await api.patch(`/api/v1/documents/${props.document.id}`, {
        title: form.title,
        content: form.content
      })
      emit('updated')
    } else {
      await api.post('/api/v1/documents', {
        patient_id: form.patient_id,
        document_type: form.document_type,
        title: form.title,
        content: form.content
      })
      emit('created')
    }
  } finally {
    saving.value = false
  }
}

// Load patients for selector
onMounted(async () => {
  const response = await api.get('/api/v1/patients?page_size=100')
  patientOptions.value = response.data.map((p: any) => ({
    label: `${p.first_name} ${p.last_name}`,
    value: p.id
  }))
})
</script>
