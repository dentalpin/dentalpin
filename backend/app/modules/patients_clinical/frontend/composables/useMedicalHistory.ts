import type {
  AllergyEntry,
  ApiResponse,
  MedicationEntry,
  MedicalHistory,
  SurgicalHistoryEntry,
  SystemicDiseaseEntry
} from '~~/app/types'

const DEFAULT_MEDICAL_HISTORY: MedicalHistory = {
  allergies: [],
  medications: [],
  systemic_diseases: [],
  surgical_history: [],
  is_pregnant: false,
  pregnancy_week: undefined,
  is_lactating: false,
  is_on_anticoagulants: false,
  anticoagulant_medication: undefined,
  inr_value: undefined,
  last_inr_date: undefined,
  is_smoker: false,
  smoking_frequency: undefined,
  alcohol_consumption: undefined,
  bruxism: false,
  adverse_reactions_to_anesthesia: false,
  anesthesia_reaction_details: undefined,
  last_updated_at: undefined,
  last_updated_by: undefined
}

export function useMedicalHistory(patientId: Ref<string | undefined>) {
  const api = useApi()
  const { t } = useI18n()
  const toast = useToast()

  const medicalHistory = ref<MedicalHistory>({ ...DEFAULT_MEDICAL_HISTORY })
  const isLoading = ref(false)
  const isSaving = ref(false)
  const error = ref<string | null>(null)

  async function fetchMedicalHistory() {
    if (!patientId.value) return

    isLoading.value = true
    error.value = null

    try {
      const response = await api.get<ApiResponse<MedicalHistory>>(
        `/api/v1/patients_clinical/patients/${patientId.value}/medical-history`
      )
      medicalHistory.value = response.data || { ...DEFAULT_MEDICAL_HISTORY }
    } catch (e) {
      error.value = t('patients.medicalHistory.fetchError')
      console.error('Failed to fetch medical history:', e)
    } finally {
      isLoading.value = false
    }
  }

  async function saveMedicalHistory(): Promise<boolean> {
    if (!patientId.value) return false

    isSaving.value = true
    error.value = null

    try {
      const response = await api.put<ApiResponse<MedicalHistory>>(
        `/api/v1/patients_clinical/patients/${patientId.value}/medical-history`,
        medicalHistory.value
      )
      medicalHistory.value = response.data
      // Cross-module refresh signal (#274): announce on the host data bus
      // that this module's data changed, so anonymous subscribers (e.g.
      // medical_reference's patient warning chips) can refetch. No
      // payload, no consumer coupling — see ADR 0021.
      useDataBus().publish('patients_clinical')
      toast.add({
        title: t('common.success'),
        description: t('patients.medicalHistory.saveSuccess'),
        color: 'success'
      })
      return true
    } catch (e) {
      error.value = t('patients.medicalHistory.saveError')
      toast.add({
        title: t('common.error'),
        description: t('patients.medicalHistory.saveError'),
        color: 'error'
      })
      console.error('Failed to save medical history:', e)
      return false
    } finally {
      isSaving.value = false
    }
  }

  // Allergy helpers
  function addAllergy(allergy: AllergyEntry) {
    medicalHistory.value.allergies.push(allergy)
  }

  function removeAllergy(index: number) {
    medicalHistory.value.allergies.splice(index, 1)
  }

  function updateAllergy(index: number, allergy: AllergyEntry) {
    medicalHistory.value.allergies[index] = allergy
  }

  // Medication helpers
  function addMedication(medication: MedicationEntry) {
    medicalHistory.value.medications.push(medication)
  }

  function removeMedication(index: number) {
    medicalHistory.value.medications.splice(index, 1)
  }

  function updateMedication(index: number, medication: MedicationEntry) {
    medicalHistory.value.medications[index] = medication
  }

  // Systemic disease helpers
  function addSystemicDisease(disease: SystemicDiseaseEntry) {
    medicalHistory.value.systemic_diseases.push(disease)
  }

  function removeSystemicDisease(index: number) {
    medicalHistory.value.systemic_diseases.splice(index, 1)
  }

  function updateSystemicDisease(index: number, disease: SystemicDiseaseEntry) {
    medicalHistory.value.systemic_diseases[index] = disease
  }

  // Surgical history helpers
  function addSurgicalHistory(entry: SurgicalHistoryEntry) {
    medicalHistory.value.surgical_history.push(entry)
  }

  function removeSurgicalHistory(index: number) {
    medicalHistory.value.surgical_history.splice(index, 1)
  }

  function updateSurgicalHistory(index: number, entry: SurgicalHistoryEntry) {
    medicalHistory.value.surgical_history[index] = entry
  }

  // Watch patientId and fetch when it changes
  watch(patientId, (newId) => {
    if (newId) {
      fetchMedicalHistory()
    } else {
      medicalHistory.value = { ...DEFAULT_MEDICAL_HISTORY }
    }
  }, { immediate: true })

  return {
    medicalHistory,
    isLoading,
    isSaving,
    error,
    fetchMedicalHistory,
    saveMedicalHistory,
    // Allergy helpers
    addAllergy,
    removeAllergy,
    updateAllergy,
    // Medication helpers
    addMedication,
    removeMedication,
    updateMedication,
    // Systemic disease helpers
    addSystemicDisease,
    removeSystemicDisease,
    updateSystemicDisease,
    // Surgical history helpers
    addSurgicalHistory,
    removeSurgicalHistory,
    updateSurgicalHistory
  }
}
