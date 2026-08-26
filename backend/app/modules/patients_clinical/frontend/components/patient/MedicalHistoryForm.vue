<script setup lang="ts">
import type { AllergyEntry, MedicationEntry, MedicalHistory, SurgicalHistoryEntry, SystemicDiseaseEntry } from '~~/app/types'

interface Props {
  modelValue: MedicalHistory
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

// Local copy for editing
const localData = computed({
  get: () => props.modelValue,
  set: value => emit('update:modelValue', value)
})

// Allergy form state
const newAllergy = ref<AllergyEntry>({
  name: '',
  type: undefined,
  severity: 'medium',
  reaction: undefined,
  notes: undefined
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
  newAllergy.value = { name: '', type: undefined, severity: 'medium', reaction: undefined, notes: undefined }
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
  notes: undefined
})

function addMedication() {
  if (!newMedication.value.name.trim()) return
  localData.value.medications.push({ ...newMedication.value })
  newMedication.value = { name: '', dosage: undefined, frequency: undefined, start_date: undefined, notes: undefined }
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
  notes: undefined
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
  newDisease.value = { name: '', type: undefined, diagnosis_date: undefined, is_controlled: true, is_critical: false, medications: undefined, notes: undefined }
}

function removeDisease(index: number) {
  localData.value.systemic_diseases.splice(index, 1)
}

// Surgical history form state
const newSurgery = ref<SurgicalHistoryEntry>({
  procedure: '',
  surgery_date: undefined,
  complications: undefined,
  notes: undefined
})

function addSurgery() {
  if (!newSurgery.value.procedure.trim()) return
  localData.value.surgical_history.push({ ...newSurgery.value })
  newSurgery.value = { procedure: '', surgery_date: undefined, complications: undefined, notes: undefined }
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

// --- Name-input extension points -----------------------------------------
/**
 * Each history-table name input is a slot extension point. Optional
 * modules (e.g. medical_reference) register a searchable combobox into
 * ``patients_clinical.medical_history.<entity>_name`` from their own
 * plugin; when nothing is registered the plain UInput fallback renders,
 * so this form never imports another module's component.
 *
 * Slot ctx contract (passed verbatim to registered components):
 *   kind       — which history entity the field feeds
 *   value      — current name text (display-only; owners keep state)
 *   placeholder/disabled — rendering hints
 *   select()   — commit a picked/created item: name + loose reference_id
 */
interface MedicalHistoryNameFieldCtx {
  kind: 'allergy' | 'medication' | 'disease' | 'surgery'
  value: string
  placeholder?: string
  disabled?: boolean
  select: (name: string, referenceId: string | null) => void
}

const { resolve } = useModuleSlots()

function useNameField(
  slotName: string,
  kind: MedicalHistoryNameFieldCtx['kind'],
  target: Ref<{ name?: string, procedure?: string, reference_id?: string | null }>,
  placeholderKey: string
) {
  const hasExtension = computed(() => resolve(slotName, {}).length > 0)
  const ctx = computed<MedicalHistoryNameFieldCtx>(() => ({
    kind,
    value: target.value.name ?? target.value.procedure ?? '',
    placeholder: t(placeholderKey),
    disabled: props.readonly,
    select: (name, referenceId) => {
      if (kind === 'surgery') {
        target.value.procedure = name
      } else {
        target.value.name = name
      }
      target.value.reference_id = referenceId ?? undefined
    }
  }))
  return { hasExtension, ctx }
}

const allergyNameField = useNameField(
  'patients_clinical.medical_history.allergy_name', 'allergy', newAllergy, 'patients.medicalHistory.allergyName'
)
const medicationNameField = useNameField(
  'patients_clinical.medical_history.medication_name', 'medication', newMedication, 'patients.medicalHistory.medicationName'
)
const diseaseNameField = useNameField(
  'patients_clinical.medical_history.disease_name', 'disease', newDisease, 'patients.medicalHistory.diseaseName'
)
const surgeryNameField = useNameField(
  'patients_clinical.medical_history.surgery_name', 'surgery', newSurgery, 'patients.medicalHistory.procedure'
)

function handleSave() {
  emit('save')
}
</script>

<template>
  <div class="medical-history-form space-y-6">
    <!-- Allergies Section -->
    <UAccordion
      :items="[{ label: t('patients.medicalHistory.allergies'), icon: 'i-lucide-alert-triangle', defaultOpen: true, slot: 'allergies' }]"
      :ui="{ item: 'border rounded-lg mb-2' }"
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
              :aria-label="t('common.delete')"
              size="xs"
              @click="removeAllergy(index)"
            />
          </div>

          <!-- Add new allergy -->
          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-4 gap-2"
          >
            <!-- Extension point: optional modules (e.g. medical_reference)
                 register a searchable combobox here; the plain input below
                 is the fallback when nothing is registered. -->
            <ModuleSlot
              v-if="allergyNameField.hasExtension.value"
              name="patients_clinical.medical_history.allergy_name"
              :ctx="allergyNameField.ctx.value"
            />
            <UInput
              v-else
              v-model="newAllergy.name"
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
      :ui="{ item: 'border rounded-lg mb-2' }"
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
              :aria-label="t('common.delete')"
              size="xs"
              @click="removeMedication(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-4 gap-2"
          >
            <!-- Extension point: see allergy section -->
            <ModuleSlot
              v-if="medicationNameField.hasExtension.value"
              name="patients_clinical.medical_history.medication_name"
              :ctx="medicationNameField.ctx.value"
            />
            <UInput
              v-else
              v-model="newMedication.name"
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
      :ui="{ item: 'border rounded-lg mb-2' }"
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
              :aria-label="t('common.delete')"
              size="xs"
              @click="removeDisease(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-3 gap-2"
          >
            <!-- Extension point: see allergy section -->
            <ModuleSlot
              v-if="diseaseNameField.hasExtension.value"
              name="patients_clinical.medical_history.disease_name"
              :ctx="diseaseNameField.ctx.value"
            />
            <UInput
              v-else
              v-model="newDisease.name"
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
      :ui="{ item: 'border rounded-lg mb-2' }"
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
      :ui="{ item: 'border rounded-lg mb-2' }"
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
      :ui="{ item: 'border rounded-lg mb-2' }"
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
              :aria-label="t('common.delete')"
              size="xs"
              @click="removeSurgery(index)"
            />
          </div>

          <div
            v-if="!readonly"
            class="grid grid-cols-1 md:grid-cols-3 gap-2"
          >
            <!-- Extension point: see allergy section -->
            <ModuleSlot
              v-if="surgeryNameField.hasExtension.value"
              name="patients_clinical.medical_history.surgery_name"
              :ctx="surgeryNameField.ctx.value"
            />
            <UInput
              v-else
              v-model="newSurgery.procedure"
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
