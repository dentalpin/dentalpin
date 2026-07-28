<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useDocuments,
  type PrescriptionItem,
  type CertificateType,
  type ReferralUrgency
} from '../../../composables/useDocuments'
// UNCONFIRMED PATH — see PHASE14_INSTALL_GUIDE.md. Inventory's real
// cross-module imports use a relative path across sibling module
// directories (e.g. `'../../../../supplier_items/frontend/components/…'`),
// not a `~/components/shared/…` alias. The alias below was never
// actually grepped from the real repo — only claimed in an earlier,
// since-contradicted message. Confirm the real location of the patient
// picker component and fix this import before relying on this page.
import PatientVisualSelector from '~/components/shared/PatientVisualSelector.vue'
// Cross-module import matching the confirmed convention (relative path
// across sibling /module_layers/ directories, e.g. inventory ->
// supplier_items). 5 "../" because this file sits 5 levels below
// /module_layers/ (documents/frontend/pages/documents/new/).
import { useMedications, type Medication } from '../../../../../medications/frontend/composables/useMedications'

definePageMeta({ middleware: ['auth'] })

const route = useRoute()
const router = useRouter()
const { t } = useI18n()
const { can } = usePermissions()
const docsApi = useDocuments()

if (!can(PERMISSIONS.documents.write)) {
  await navigateTo('/')
}

// route.params.type is one of: prescription | certificate | referral | radiology-request
const type = computed(() => route.params.type as string)

// PatientVisualSelector emits the full Patient object via v-model, not a bare id
const selectedPatient = ref<{ id: string } | null>(null)
const patientId = computed(() => selectedPatient.value?.id ?? null)

const saving = ref(false)
const error = ref<string | null>(null)

// prescription
const items = ref<PrescriptionItem[]>([{ drug_name: '', dosage: '', instructions: '', quantity: '', medication_id: null }])
const prescriptionNotes = ref('')

const medicationsApi = useMedications()
const MANUAL_ENTRY = '__manual__'
const medicationCatalog = ref<Medication[]>([])
const medicationOptions = ref<Array<{ value: string, label: string }>>([{ value: MANUAL_ENTRY, label: '' }])

async function loadMedications() {
  try {
    const res = await medicationsApi.list({ page_size: 100, is_prescribed: true })
    medicationCatalog.value = res.data
    medicationOptions.value = [
      { value: MANUAL_ENTRY, label: t('documents.form.manualEntry') },
      ...res.data.map(m => ({
        value: m.id,
        label: `${m.name} — ${m.dose}${m.unit} (${t(`documents.form.medForm.${m.form}`)})`
      }))
    ]
  } catch {
    // Catalog fetch failing shouldn't block manual prescribing — leave
    // it as manual-only so the item row just falls back to free text.
    medicationOptions.value = [{ value: MANUAL_ENTRY, label: t('documents.form.manualEntry') }]
  }
}

function onMedicationPicked(item: PrescriptionItem, medicationId: string) {
  if (medicationId === MANUAL_ENTRY) {
    item.medication_id = null
    return
  }
  const med = medicationCatalog.value.find(m => m.id === medicationId)
  if (!med) return
  item.medication_id = med.id
  item.drug_name = `${med.name} (${med.dose}${med.unit})`
  item.instructions = med.instructions
    ? `${med.instructions}${med.times_per_day ? ` — ${med.times_per_day}x/${t('documents.form.perDay')}` : ''}`
    : (med.times_per_day ? `${med.times_per_day}x/${t('documents.form.perDay')}` : '')
  // dosage/quantity are left for the practitioner to fill in per-patient
  // (the catalog only stores the drug's own strength, not a prescribed
  // regimen) — auto-filling drug_name/instructions is the safe part.
}

// certificate
const certificateType = ref<CertificateType>('work_absence')
const certificateTypeOptions = computed(() => [
  { value: 'work_absence', label: t('documents.certificate.work_absence') },
  { value: 'school_absence', label: t('documents.certificate.school_absence') },
  { value: 'fitness_for_work', label: t('documents.certificate.fitness_for_work') }
])
const startDate = ref('')
const endDate = ref('')
const certificateReason = ref('')
const certificateNotes = ref('')

// referral
const specialistName = ref('')
const SPECIALTY_KEYS = [
  // Dental specialties
  'orthodontics', 'endodontics', 'periodontics', 'oral_maxillofacial_surgery',
  'pediatric_dentistry', 'prosthodontics', 'oral_pathology', 'oral_medicine',
  'implantology',
  // General medicine specialties a dentist commonly refers to
  'cardiology', 'endocrinology_diabetes', 'rheumatology', 'ent',
  'internal_medicine', 'hematology', 'allergy_immunology', 'psychiatry',
  'anesthesiology', 'pediatrics'
]
const specialtyOptions = computed(() => [
  ...SPECIALTY_KEYS.map(k => ({ value: k, label: t(`documents.specialties.${k}`) })),
  { value: 'other', label: t('documents.form.other') }
])
const specialty = ref('')
const specialtyOther = ref('')
const referralReason = ref('')
const clinicalHistory = ref('')
const urgency = ref<ReferralUrgency>('routine')
const urgencyOptions = computed(() => [
  { value: 'routine', label: t('documents.form.routine') },
  { value: 'urgent', label: t('documents.form.urgent') }
])

// radiology
const EXAM_TYPE_KEYS = [
  'panoramic', 'periapical', 'bitewing', 'occlusal', 'cephalometric', 'cbct', 'tmj_view'
]
const examTypeOptions = computed(() => [
  ...EXAM_TYPE_KEYS.map(k => ({ value: k, label: t(`documents.examTypes.${k}`) })),
  { value: 'other', label: t('documents.form.other') }
])
const examType = ref('')
const examTypeOther = ref('')
const toothReference = ref('')
const clinicalIndication = ref('')
const radiologyNotes = ref('')

const itemPicks = ref<string[]>([MANUAL_ENTRY])

function addItem() {
  items.value.push({ drug_name: '', dosage: '', instructions: '', quantity: '', medication_id: null })
  itemPicks.value.push(MANUAL_ENTRY)
}
function removeItem(index: number) {
  items.value.splice(index, 1)
  itemPicks.value.splice(index, 1)
}
function pickMedication(index: number, medicationId: string) {
  itemPicks.value[index] = medicationId
  onMedicationPicked(items.value[index], medicationId)
}

onMounted(() => {
  if (type.value === 'prescription') loadMedications()
})

async function submit() {
  if (!patientId.value) {
    error.value = t('documents.form.errors.patient_required')
    return
  }
  saving.value = true
  error.value = null
  try {
    let doc
    if (type.value === 'prescription') {
      doc = await docsApi.createPrescription({
        patient_id: patientId.value,
        items: items.value,
        notes: prescriptionNotes.value || null
      })
    } else if (type.value === 'certificate') {
      doc = await docsApi.createCertificate({
        patient_id: patientId.value,
        certificate_type: certificateType.value,
        start_date: startDate.value,
        end_date: endDate.value || null,
        reason: certificateReason.value || null,
        notes: certificateNotes.value || null
      })
    } else if (type.value === 'referral') {
      doc = await docsApi.createReferral({
        patient_id: patientId.value,
        specialist_name: specialistName.value,
        specialty: specialty.value === 'other' ? specialtyOther.value : t(`documents.specialties.${specialty.value}`),
        reason: referralReason.value,
        clinical_history: clinicalHistory.value || null,
        urgency: urgency.value
      })
    } else if (type.value === 'radiology-request') {
      doc = await docsApi.createRadiologyRequest({
        patient_id: patientId.value,
        exam_type: examType.value === 'other' ? examTypeOther.value : t(`documents.examTypes.${examType.value}`),
        tooth_reference: toothReference.value || null,
        clinical_indication: clinicalIndication.value,
        notes: radiologyNotes.value || null
      })
    }
    if (doc) {
      await docsApi.downloadPdf(doc.data)
      router.push('/documents')
    }
  } catch (e: any) {
    error.value = e?.data?.detail || t('documents.form.errors.generic')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="p-4 space-y-4 max-w-2xl">
    <UButton icon="i-lucide-arrow-left" variant="ghost" size="sm" to="/documents">
      {{ t('documents.form.back') }}
    </UButton>

    <h1 class="text-h2 text-default">
      {{ t(`documents.new.${type.replace('-', '_')}`) }}
    </h1>

    <div class="space-y-1">
      <label class="text-sm font-medium">{{ t('documents.form.patient') }}</label>
      <PatientVisualSelector v-model="selectedPatient" />
    </div>

    <template v-if="type === 'prescription'">
      <div v-for="(item, i) in items" :key="i" class="border rounded-md p-2 space-y-2">
        <USelect
          :model-value="itemPicks[i]"
          :items="medicationOptions"
          :placeholder="t('documents.form.selectFromCatalog')"
          @update:model-value="(v: string) => pickMedication(i, v)"
        />
        <div class="flex flex-wrap gap-2 items-center">
          <UInput v-model="item.drug_name" :placeholder="t('documents.form.drug_name')" />
          <UInput v-model="item.dosage" :placeholder="t('documents.form.dosage')" />
          <UInput v-model="item.instructions" :placeholder="t('documents.form.instructions')" />
          <UInput v-model="item.quantity" :placeholder="t('documents.form.quantity')" />
          <UButton icon="i-lucide-x" variant="ghost" size="xs" @click="removeItem(i)" />
        </div>
      </div>
      <UButton icon="i-lucide-plus" variant="outline" size="sm" @click="addItem">
        {{ t('documents.form.add_item') }}
      </UButton>
      <UTextarea v-model="prescriptionNotes" :placeholder="t('documents.form.notes')" />
    </template>

    <template v-else-if="type === 'certificate'">
      <USelect v-model="certificateType" :items="certificateTypeOptions" />
      <UInput v-model="startDate" type="date" />
      <UInput v-model="endDate" type="date" />
      <UTextarea v-model="certificateReason" :placeholder="t('documents.form.reason')" />
      <UTextarea v-model="certificateNotes" :placeholder="t('documents.form.notes')" />
    </template>

    <template v-else-if="type === 'referral'">
      <UInput v-model="specialistName" :placeholder="t('documents.form.specialist_name')" />
      <USelect v-model="specialty" :items="specialtyOptions" :placeholder="t('documents.form.specialty')" />
      <UInput v-if="specialty === 'other'" v-model="specialtyOther" :placeholder="t('documents.form.specialty')" />
      <USelect v-model="urgency" :items="urgencyOptions" />
      <UTextarea v-model="referralReason" :placeholder="t('documents.form.reason')" />
      <UTextarea v-model="clinicalHistory" :placeholder="t('documents.form.clinical_history')" />
    </template>

    <template v-else-if="type === 'radiology-request'">
      <USelect v-model="examType" :items="examTypeOptions" :placeholder="t('documents.form.exam_type')" />
      <UInput v-if="examType === 'other'" v-model="examTypeOther" :placeholder="t('documents.form.exam_type')" />
      <UInput v-model="toothReference" :placeholder="t('documents.form.tooth_reference')" />
      <UTextarea v-model="clinicalIndication" :placeholder="t('documents.form.clinical_indication')" />
      <UTextarea v-model="radiologyNotes" :placeholder="t('documents.form.notes')" />
    </template>

    <p v-if="error" class="text-error text-sm">{{ error }}</p>

    <UButton :loading="saving" @click="submit">
      {{ saving ? t('documents.form.saving') : t('documents.form.generate') }}
    </UButton>
  </div>
</template>
