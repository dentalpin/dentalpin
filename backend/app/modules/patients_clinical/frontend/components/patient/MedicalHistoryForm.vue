<script setup lang="ts">
import type { AllergyEntry, MedicationEntry, MedicalHistory, SurgicalHistoryEntry, SystemicDiseaseEntry } from '~~/app/types'

interface Props {
  modelValue: MedicalHistory
  patientId?: string
  readonly?: boolean
  hideActions?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  readonly: false,
  hideActions: false
})

const emit = defineEmits<{
  'update:modelValue': [value: MedicalHistory]
  'save': []
}>()

const { t } = useI18n()
const { search: searchMedicalReference, fetchPatientFlags } = useMedicalReference()

// Active interaction/contraindication warnings for this patient — computed
// server-side from whichever of their medications/diseases have a
// reference_id (free-text-only legacy entries can't be reliably matched,
// see MedicalReferenceService.get_patient_flags).
const flags = ref<{ type: string, risk_note: string, involved: string[] }[]>([])
async function loadFlags() {
  if (!props.patientId) return
  flags.value = await fetchPatientFlags(props.patientId)
}
onMounted(loadFlags)
// Re-check whenever the medication or disease list changes — covers both
// adding a new entry and removing one that was causing a flag.
watch(
  () => [props.modelValue.medications.length, props.modelValue.systemic_diseases.length],
  loadFlags
)

// Local copy for editing
const localData = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

// APCI check — fetched once, matched against a disease row's reference_id
// first, falling back to a case-insensitive name match for legacy
// free-text entries that predate this column.
const apciDiseases = ref<{ id: string, name: string }[]>([])
onMounted(async () => {
  apciDiseases.value = (await searchMedicalReference('diseases', '')).filter(d => d.is_apci)
})
const apciIds = computed(() => new Set(apciDiseases.value.map(d => d.id)))
const apciNames = computed(() => new Set(apciDiseases.value.map(d => d.name.toLowerCase())))
function isApci(disease: SystemicDiseaseEntry): boolean {
  if (disease.reference_id) return apciIds.value.has(disease.reference_id)
  return apciNames.value.has(disease.name.toLowerCase())
}

// Allergy form state
const newAllergy = ref<AllergyEntry>({
  name: '',
  type: undefined,
  severity: 'medium',
  reaction: undefined,
  notes: undefined,
  reference_id: undefined
})

const allergyTypes = computed(() => [
  { label: t('patients.medicalHistory.allergyTypes.drug'), value: 'drug' },
  { label: t('patients.medicalHistory.allergyTypes.food'), value: 'food' },
  { label: t('patients.medicalHistory.allergyTypes.material'), value: 'material' },
  { label: t('patients.medicalHistory.allergyTypes.environmental'), value: 'environmental' }
])

const severityOptions = computed(() => [
  { label: t('patients.medicalHistory.severity.low'), value: 'low' },
  { label: t('patients.medicalHistory.severity.medium'), value: 'medium' },
  { label: t('patients.medicalHistory.severity.high'), value: 'high' },
  { label: t('patients.medicalHistory.severity.critical'), value: 'critical' }
])

function addAllergy() {
  if (!newAllergy.value.name.trim()) return
  localData.value.allergies.push({ ...newAllergy.value })
  newAllergy.value = { name: '', type: undefined, severity: 'medium', reaction: undefined, notes: undefined, reference_id: undefined }
}

function removeAllergy(index: number) {
  localData.value.allergies.splice(index, 1)
}

// Medication form state
const newMedication = ref<MedicationEntry>({
  name: '',
  dosage: undefined,
  frequency: undefined,
  start_date: undefined,
  notes: undefined,
  reference_id: undefined
})

function addMedication() {
  if (!newMedication.value.name.trim()) return
  localData.value.medications.push({ ...newMedication.value })
  newMedication.value = { name: '', dosage: undefined, frequency: undefined, start_date: undefined, notes: undefined, reference_id: undefined }
}

function removeMedication(index: number) {
  localData.value.medications.splice(index, 1)
}

// Systemic disease form state
const newDisease = ref<SystemicDiseaseEntry>({
  name: '',
  type: undefined,
  diagnosis_date: undefined,
  is_controlled: true,
  is_critical: false,
  medications: undefined,
  notes: undefined,
  reference_id: undefined
})

const diseaseTypes = computed(() => [
  { label: t('patients.medicalHistory.diseaseTypes.cardiovascular'), value: 'cardiovascular' },
  { label: t('patients.medicalHistory.diseaseTypes.respiratory'), value: 'respiratory' },
  { label: t('patients.medicalHistory.diseaseTypes.endocrine'), value: 'endocrine' },
  { label: t('patients.medicalHistory.diseaseTypes.neurological'), value: 'neurological' },
  { label: t('patients.medicalHistory.diseaseTypes.autoimmune'), value: 'autoimmune' },
  { label: t('patients.medicalHistory.diseaseTypes.other'), value: 'other' }
])

function addDisease() {
  if (!newDisease.value.name.trim()) return
  localData.value.systemic_diseases.push({ ...newDisease.value })
  newDisease.value = { name: '', type: undefined, diagnosis_date: undefined, is_controlled: true, is_critical: false, medications: undefined, notes: undefined, reference_id: undefined }
}

function removeDisease(index: number) {
  localData.value.systemic_diseases.splice(index, 1)
}

// Surgical history form state
const newSurgery = ref<SurgicalHistoryEntry>({
  procedure: '',
  surgery_date: undefined,
  complications: undefined,
  notes: undefined,
  reference_id: undefined
})

function addSurgery() {
  if (!newSurgery.value.procedure.trim()) return
  localData.value.surgical_history.push({ ...newSurgery.value })
  newSurgery.value = { procedure: '', surgery_date: undefined, complications: undefined, notes: undefined, reference_id: undefined }
}

function removeSurgery(index: number) {
  localData.value.surgical_history.splice(index, 1)
}

// Alcohol options
const alcoholOptions = computed(() => [
  { label: t('patients.medicalHistory.alcohol.none'), value: 'none' },
  { label: t('patients.medicalHistory.alcohol.occasional'), value: 'occasional' },
  { label: t('patients.medicalHistory.alcohol.moderate'), value: 'moderate' },
  { label: t('patients.medicalHistory.alcohol.heavy'), value: 'heavy' }
])

function handleSave() {
  emit('save')
}
</script>

<template>
  <div class="medical-history-form space-y-6">
    <!-- Active interaction/contraindication warnings -->
    <UAlert
      v-if="flags.length > 0"
      color="error"
      variant="subtle"
      icon="i-lucide-alert-octagon"
      :title="t('patients.medicalHistory.warningsTitle')"
    >
      <template #description>
        <ul class="space-y-1 mt-1">
          <li
            v-for="(flag, i) in flags"
            :key="i"
          >
            <span class="font-medium">{{ flag.involved.join(' + ') }}</span>
            — {{ flag.risk_note }}
          </li>
        </ul>
      </template>
    </UAlert>

    <!-- Allergies Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.allergies'), icon: 'i-lucide-alert-triangle', defaultOpen: true, slot: 'allergies' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #allergies>
        <div class="p-4 space-y-4">
          <!-- Existing allergies -->
          <div
            v-for="(allergy, index) in localData.allergies"
            :key="index"
            class="flex items-center gap-2 p-2 bg-surface-muted rounded"
          >
            <UBadge
              :color="allergy.severity === 'critical' ? 'error' : allergy.severity === 'high' ? 'warning' : 'info'"
              size="xs"
            >
              {{ allergy.severity }}
            </UBadge>
            <span class="flex-1 font-medium">{{ allergy.name }}</span>
            <span
              v-if="allergy.type"
              class="text-caption text-subtle"
            >{{ allergy.type }}</span>
            <UButton
              v-if="!readonly"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              @click="removeAllergy(index)"
            />
          </div>

          <!-- Add new allergy -->
          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-4 gap-2"
          >
            <ReferenceSearchInput
              v-model="newAllergy.name"
              v-model:reference-id="newAllergy.reference_id"
              kind="allergies"
              :placeholder="t('patients.medicalHistory.allergyName')"
            />
            <USelect
              v-model="newAllergy.type"
              :items="allergyTypes"
              value-key="value"
              label-key="label"
              :placeholder="t('patients.medicalHistory.type')"
            />
            <USelect
              v-model="newAllergy.severity"
              :items="severityOptions"
              value-key="value"
              label-key="label"
            />
            <UButton
              icon="i-lucide-plus"
              @click="addAllergy"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </UAccordion>

    <!-- Current Medications Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.medications'), icon: 'i-lucide-pill', defaultOpen: false, slot: 'medications' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #medications>
        <div class="p-4 space-y-4">
          <div
            v-for="(med, index) in localData.medications"
            :key="index"
            class="flex items-center gap-2 p-2 bg-surface-muted rounded"
          >
            <span class="flex-1 font-medium">{{ med.name }}</span>
            <span
              v-if="med.dosage"
              class="text-caption text-subtle"
            >{{ med.dosage }}</span>
            <span
              v-if="med.frequency"
              class="text-caption text-subtle"
            >{{ med.frequency }}</span>
            <UButton
              v-if="!readonly"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              @click="removeMedication(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-4 gap-2"
          >
            <ReferenceSearchInput
              v-model="newMedication.name"
              v-model:reference-id="newMedication.reference_id"
              kind="medications"
              :placeholder="t('patients.medicalHistory.medicationName')"
            />
            <UInput
              v-model="newMedication.dosage"
              :placeholder="t('patients.medicalHistory.dosage')"
            />
            <UInput
              v-model="newMedication.frequency"
              :placeholder="t('patients.medicalHistory.frequency')"
            />
            <UButton
              icon="i-lucide-plus"
              @click="addMedication"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </UAccordion>

    <!-- Systemic Diseases Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.systemicDiseases'), icon: 'i-lucide-activity', defaultOpen: false, slot: 'diseases' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #diseases>
        <div class="p-4 space-y-4">
          <div
            v-for="(disease, index) in localData.systemic_diseases"
            :key="index"
            class="flex items-center gap-2 p-2 bg-surface-muted rounded"
          >
            <UBadge
              v-if="disease.is_critical"
              color="error"
              size="xs"
            >
              {{ t('patients.medicalHistory.critical') }}
            </UBadge>
            <UBadge
              v-if="isApci(disease)"
              color="info"
              size="xs"
            >
              APCI
            </UBadge>
            <span class="flex-1 font-medium">{{ disease.name }}</span>
            <UBadge
              :color="disease.is_controlled ? 'success' : 'warning'"
              size="xs"
            >
              {{ disease.is_controlled ? t('patients.medicalHistory.controlled') : t('patients.medicalHistory.notControlled') }}
            </UBadge>
            <UButton
              v-if="!readonly"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              @click="removeDisease(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-3 gap-2"
          >
            <ReferenceSearchInput
              v-model="newDisease.name"
              v-model:reference-id="newDisease.reference_id"
              kind="diseases"
              :placeholder="t('patients.medicalHistory.diseaseName')"
            />
            <USelect
              v-model="newDisease.type"
              :items="diseaseTypes"
              value-key="value"
              label-key="label"
              :placeholder="t('patients.medicalHistory.type')"
            />
            <div class="flex gap-2 items-center">
              <UCheckbox
                v-model="newDisease.is_critical"
                :label="t('patients.medicalHistory.critical')"
              />
              <UButton
                icon="i-lucide-plus"
                @click="addDisease"
              >
                {{ t('common.add') }}
              </UButton>
            </div>
          </div>
        </div>
      </template>
    </UAccordion>

    <!-- Special Conditions Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.specialConditions'), icon: 'i-lucide-heart-pulse', defaultOpen: true, slot: 'conditions' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #conditions>
        <div class="p-4 space-y-4">
          <!-- Pregnancy -->
          <div class="flex flex-wrap items-center gap-4">
            <UCheckbox
              v-model="localData.is_pregnant"
              :label="t('patients.medicalHistory.pregnant')"
              :disabled="readonly"
            />
            <UInput
              v-if="localData.is_pregnant"
              v-model.number="localData.pregnancy_week"
              type="number"
              :min="1"
              :max="42"
              :placeholder="t('patients.medicalHistory.pregnancyWeek')"
              class="w-32"
              :disabled="readonly"
            />
          </div>

          <!-- Lactating -->
          <UCheckbox
            v-model="localData.is_lactating"
            :label="t('patients.medicalHistory.lactating')"
            :disabled="readonly"
          />

          <!-- Anticoagulants -->
          <div class="space-y-2">
            <UCheckbox
              v-model="localData.is_on_anticoagulants"
              :label="t('patients.medicalHistory.anticoagulants')"
              :disabled="readonly"
            />
            <div
              v-if="localData.is_on_anticoagulants"
              class="ml-6 grid grid-cols-1 md:grid-cols-3 gap-2"
            >
              <UInput
                v-model="localData.anticoagulant_medication"
                :placeholder="t('patients.medicalHistory.anticoagulantMedication')"
                :disabled="readonly"
              />
              <UInput
                v-model.number="localData.inr_value"
                type="number"
                step="0.1"
                :placeholder="t('patients.medicalHistory.inrValue')"
                :disabled="readonly"
              />
              <UInput
                v-model="localData.last_inr_date"
                type="date"
                :disabled="readonly"
              />
            </div>
          </div>

          <!-- Anesthesia reaction -->
          <div class="space-y-2">
            <UCheckbox
              v-model="localData.adverse_reactions_to_anesthesia"
              :label="t('patients.medicalHistory.anesthesiaReaction')"
              :disabled="readonly"
            />
            <UInput
              v-if="localData.adverse_reactions_to_anesthesia"
              v-model="localData.anesthesia_reaction_details"
              :placeholder="t('patients.medicalHistory.anesthesiaReactionDetails')"
              class="ml-6"
              :disabled="readonly"
            />
          </div>

          <!-- Bruxism -->
          <UCheckbox
            v-model="localData.bruxism"
            :label="t('patients.medicalHistory.bruxism')"
            :disabled="readonly"
          />
        </div>
      </template>
    </UAccordion>

    <!-- Lifestyle Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.lifestyle'), icon: 'i-lucide-cigarette', defaultOpen: false, slot: 'lifestyle' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #lifestyle>
        <div class="p-4 space-y-4">
          <div class="flex flex-wrap items-center gap-4">
            <UCheckbox
              v-model="localData.is_smoker"
              :label="t('patients.medicalHistory.smoker')"
              :disabled="readonly"
            />
            <UInput
              v-if="localData.is_smoker"
              v-model="localData.smoking_frequency"
              :placeholder="t('patients.medicalHistory.smokingFrequency')"
              class="w-48"
              :disabled="readonly"
            />
          </div>

          <div class="flex items-center gap-4">
            <span class="text-sm">{{ t('patients.medicalHistory.alcoholConsumption') }}:</span>
            <USelect
              v-model="localData.alcohol_consumption"
              :items="alcoholOptions"
              value-key="value"
              label-key="label"
              class="w-48"
              :disabled="readonly"
            />
          </div>
        </div>
      </template>
    </UAccordion>

    <!-- Surgical History Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.surgicalHistory'), icon: 'i-lucide-scissors', defaultOpen: false, slot: 'surgery' }]"
      :ui="{ item: { base: 'border rounded-lg mb-2' } }"
    >
      <template #surgery>
        <div class="p-4 space-y-4">
          <div
            v-for="(surgery, index) in localData.surgical_history"
            :key="index"
            class="flex items-center gap-2 p-2 bg-surface-muted rounded"
          >
            <span class="flex-1 font-medium">{{ surgery.procedure }}</span>
            <span
              v-if="surgery.surgery_date"
              class="text-caption text-subtle"
            >{{ surgery.surgery_date }}</span>
            <UButton
              v-if="!readonly"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              @click="removeSurgery(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-3 gap-2"
          >
            <ReferenceSearchInput
              v-model="newSurgery.procedure"
              v-model:reference-id="newSurgery.reference_id"
              kind="surgeries"
              :placeholder="t('patients.medicalHistory.procedure')"
            />
            <UInput
              v-model="newSurgery.surgery_date"
              type="date"
            />
            <UButton
              icon="i-lucide-plus"
              @click="addSurgery"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </UAccordion>

    <!-- Save Button (shown only when not readonly and hideActions is false) -->
    <div
      v-if="!readonly && !hideActions"
      class="flex justify-end pt-4"
    >
      <UButton
        color="primary"
        icon="i-lucide-save"
        @click="handleSave"
      >
        {{ t('common.save') }}
      </UButton>
    </div>
  </div>
</template>
