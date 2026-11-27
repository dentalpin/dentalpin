<template>
  <UModal
    :open="open"
    :title="isEditing ? t('documents.editDocument') : t('documents.newDocument')"
    @update:open="$emit('update:open', $event)"
  >
    <template #body>
      <div class="space-y-4">
        <!-- Patient selector — server-side search, UInputMenu pattern (#208) -->
        <UFormField
          :label="t('documents.patient')"
          required
        >
          <UInputMenu
            v-model="selectedPatient"
            v-model:search-term="searchTerm"
            :items="patientOptions"
            :loading="isSearching"
            ignore-filter
            icon="i-lucide-search"
            :placeholder="t('documents.selectPatient')"
          />
          <p
            v-if="searchResultsEmpty"
            class="text-sm text-muted-foreground"
          >
            {{ t('documents.patientSearchEmpty') }}
          </p>
        </UFormField>

        <!-- Document type -->
        <UFormField
          :label="t('documents.type')"
          required
        >
          <USelect
            v-model="form.document_type"
            :items="documentTypeOptions"
            :placeholder="t('documents.selectType')"
            :disabled="isEditing"
          />
        </UFormField>

        <!-- Title -->
        <UFormField
          :label="t('documents.titleLabel')"
          required
        >
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
              <UInput
                v-model="med.name"
                :placeholder="t('documents.content.medName')"
              />
              <UInput
                v-model="med.dose"
                :placeholder="t('documents.content.medDose')"
              />
              <UInput
                v-model="med.frequency"
                :placeholder="t('documents.content.medFrequency')"
              />
              <UInput
                v-model="med.duration"
                :placeholder="t('documents.content.medDuration')"
              />
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
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          variant="ghost"
          @click="$emit('update:open', false)"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          :loading="saving"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ t('common.save') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { Patient, PaginatedResponse, ApiResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

const props = defineProps<{
  open: boolean
  document?: ManagedDocument | null
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'created': []
  'updated': []
}>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()
const { createDocument, updateDocument } = useManagedDocuments()

const isEditing = computed(() => !!props.document)
const saving = ref(false)

interface DocumentFormContent {
  diagnosis: string
  medications: MedicationDraft[]
  notes: string
  description: string
  recommendations: string
  referred_to: string
  specialty: string
  reason: string
  clinical_summary: string
  exam_type: string
  region: string
  clinical_question: string
}

function emptyContent(): DocumentFormContent {
  return {
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

// Form state
const form = reactive({
  patient_id: '',
  document_type: 'prescription' as GeneratedDocumentType,
  title: '',
  content: emptyContent()
})

// Patient picker — debounced server-side search, UInputMenu pattern (#208).
interface PatientOption {
  label: string
  id: string
}

const selectedPatient = ref<PatientOption | undefined>(undefined)
const searchTerm = ref('')
const patientOptions = ref<PatientOption[]>([])
const isSearching = ref(false)
let searchTimeout: ReturnType<typeof setTimeout> | null = null

const searchResultsEmpty = computed(
  () => searchTerm.value.length >= 2 && !isSearching.value && patientOptions.value.length === 0
)

watch(searchTerm, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (val.length < 2) {
    patientOptions.value = []
    return
  }
  searchTimeout = setTimeout(() => searchPatients(val), 300)
})

async function searchPatients(query: string) {
  isSearching.value = true
  try {
    const params = new URLSearchParams({ search: query, page: '1', page_size: '10' })
    const res = await api.get<PaginatedResponse<Patient>>(`/api/v1/patients?${params.toString()}`)
    patientOptions.value = res.data
      .filter(p => p.id !== form.patient_id)
      .map(p => ({ label: `${p.last_name}, ${p.first_name}`, id: p.id }))
    // If the current selection no longer matches the search, keep showing it.
    if (selectedPatient.value && !patientOptions.value.some(o => o.id === selectedPatient.value?.id)) {
      patientOptions.value.unshift(selectedPatient.value)
    }
  } catch {
    patientOptions.value = []
  } finally {
    isSearching.value = false
  }
}

watch(selectedPatient, (sel) => {
  form.patient_id = sel?.id ?? ''
})

// (Re)initialise the form on every opening, not only when `document`
// changes: "New document" passes null each time, so a create or a
// cancelled draft would otherwise come back on the next opening (#1232).
watch(
  [() => props.open, () => props.document],
  ([open, doc]) => {
    if (!open) return
    if (doc) {
      form.patient_id = doc.patient_id
      form.document_type = doc.document_type
      form.title = doc.title
      form.content = { ...emptyContent(), ...(doc.content as Partial<DocumentFormContent>) }
      selectedPatient.value = { id: doc.patient_id, label: '' }
      // Resolve the patient name so the UInputMenu shows a label in edit mode.
      api.get<ApiResponse<Patient>>(`/api/v1/patients/${doc.patient_id}`).then((res) => {
        const p = res.data
        selectedPatient.value = { id: p.id, label: `${p.first_name} ${p.last_name}` }
      }).catch(() => { /* label stays blank; id is what matters */ })
    } else {
      form.patient_id = ''
      form.document_type = 'prescription'
      form.title = ''
      form.content = emptyContent()
      selectedPatient.value = undefined
      searchTerm.value = ''
      patientOptions.value = []
    }
  },
  { immediate: true }
)

// Options
const documentTypeOptions = computed(() => [
  { label: t('documents.types.prescription'), value: 'prescription' },
  { label: t('documents.types.medical_certificate'), value: 'medical_certificate' },
  { label: t('documents.types.referral'), value: 'referral' },
  { label: t('documents.types.radiology_request'), value: 'radiology_request' }
])

// Client-side validation — save disabled until the minimal invariants
// hold; the server is the authority for everything else.
const canSubmit = computed(() => {
  return !!form.patient_id && form.title.trim().length > 0
})

// Methods
function addMedication() {
  form.content.medications.push({ name: '', dose: '', frequency: '', duration: '', notes: '' })
}

async function submit() {
  saving.value = true
  try {
    if (isEditing.value && props.document) {
      await updateDocument(props.document.id, {
        title: form.title,
        content: form.content
      })
      toast.add({ title: t('documents.messages.updated'), color: 'success' })
      emit('updated')
    } else {
      await createDocument({
        patient_id: form.patient_id,
        document_type: form.document_type,
        title: form.title,
        content: form.content
      })
      toast.add({ title: t('documents.messages.created'), color: 'success' })
      emit('created')
    }
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>
