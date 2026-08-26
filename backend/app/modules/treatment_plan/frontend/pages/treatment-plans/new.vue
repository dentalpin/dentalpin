<script setup lang="ts">
import type { Patient } from '~~/app/types'

const router = useRouter()
const { t } = useI18n()
const { createPlan, loading } = useTreatmentPlans()
const { professionals, fetchProfessionals } = useProfessionals()
const api = useApi()

// Patient search
const searchQuery = ref('')
const patients = ref<Patient[]>([])
const selectedPatient = ref<Patient | null>(null)
const searchLoading = ref(false)

// Form data
const form = ref({
  title: '',
  assigned_professional_id: undefined as string | undefined,
  diagnosis_notes: '',
  internal_notes: ''
})

// Fetch professionals on mount
onMounted(() => {
  fetchProfessionals()
})

// Search patients
async function searchPatients(query: string) {
  if (!query || query.length < 2) {
    patients.value = []
    return
  }

  searchLoading.value = true
  try {
    const response = await api.get<{ data: Patient[] }>(
      `/api/v1/patients?search=${encodeURIComponent(query)}&page_size=10`
    )
    patients.value = response.data
  } catch {
    patients.value = []
  } finally {
    searchLoading.value = false
  }
}

// Debounced search
let searchTimeout: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    searchPatients(val)
  }, 300)
})

function selectPatient(patient: Patient) {
  selectedPatient.value = patient
  searchQuery.value = ''
  patients.value = []
}

function clearPatient() {
  selectedPatient.value = null
}

const professionalOptions = computed(() => {
  return professionals.value.map(p => ({
    label: `${p.first_name} ${p.last_name}`,
    value: p.id
  }))
})

async function handleSubmit() {
  if (!selectedPatient.value) return

  const plan = await createPlan({
    patient_id: selectedPatient.value.id,
    title: form.value.title || undefined,
    assigned_professional_id: form.value.assigned_professional_id || undefined,
    diagnosis_notes: form.value.diagnosis_notes || undefined,
    internal_notes: form.value.internal_notes || undefined
  })

  if (plan) {
    router.push(`/treatment-plans/${plan.id}`)
  }
}

function goBack() {
  router.push('/treatment-plans')
}
</script>

<template>
  <div class="max-w-2xl mx-auto space-y-6">
    <!-- Header -->
    <div class="flex items-center gap-4">
      <UButton
        variant="ghost"
        color="neutral"
        icon="i-lucide-arrow-left"
        :aria-label="t('common.back')"
        @click="goBack"
      />
      <h1 class="text-display text-default">
        {{ t('treatmentPlans.create') }}
      </h1>
    </div>

    <UCard>
      <form
        class="space-y-6"
        @submit.prevent="handleSubmit"
      >
        <!-- Patient selection -->
        <UFormField
          :label="t('treatmentPlans.patient')"
          required
        >
          <!-- Selected patient -->
          <div
            v-if="selectedPatient"
            class="flex items-center justify-between p-3 bg-surface-muted rounded-lg"
          >
            <div>
              <p class="font-medium">
                {{ selectedPatient.last_name }}, {{ selectedPatient.first_name }}
              </p>
              <p class="text-caption text-subtle">
                {{ selectedPatient.phone }}
              </p>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.clear')"
              size="sm"
              @click="clearPatient"
            />
          </div>

          <!-- Search input -->
          <div
            v-else
            class="relative"
          >
            <UInput
              v-model="searchQuery"
              :placeholder="t('patients.searchPlaceholder')"
              icon="i-lucide-search"
              :loading="searchLoading"
            />

            <!-- Search results dropdown -->
            <div
              v-if="patients.length > 0"
              class="absolute z-10 mt-1 w-full bg-surface border border-default rounded-lg shadow-lg max-h-60 overflow-auto"
            >
              <button
                v-for="patient in patients"
                :key="patient.id"
                type="button"
                class="w-full px-4 py-2 text-left hover:bg-surface-muted"
                @click="selectPatient(patient)"
              >
                <p class="font-medium">
                  {{ patient.last_name }}, {{ patient.first_name }}
                </p>
                <p class="text-caption text-subtle">
                  {{ patient.phone }}
                </p>
              </button>
            </div>
          </div>
        </UFormField>

        <!-- Title -->
        <UFormField :label="t('treatmentPlans.fields.title')">
          <UInput
            v-model="form.title"
            :placeholder="t('treatmentPlans.fields.titlePlaceholder')"
          />
        </UFormField>

        <!-- Assigned professional -->
        <UFormField :label="t('treatmentPlans.fields.assignedProfessional')">
          <USelect
            v-model="form.assigned_professional_id"
            :items="professionalOptions"
            :placeholder="t('treatmentPlans.fields.selectProfessional')"
            value-key="value"
          />
        </UFormField>

        <!-- Diagnosis notes -->
        <UFormField :label="t('treatmentPlans.fields.diagnosisNotes')">
          <UTextarea
            v-model="form.diagnosis_notes"
            :rows="3"
            :placeholder="t('treatmentPlans.fields.diagnosisNotesPlaceholder')"
          />
        </UFormField>

        <!-- Internal notes -->
        <UFormField :label="t('treatmentPlans.fields.internalNotes')">
          <UTextarea
            v-model="form.internal_notes"
            :rows="3"
            :placeholder="t('treatmentPlans.fields.internalNotesPlaceholder')"
          />
        </UFormField>

        <!-- Actions -->
        <div class="flex justify-end gap-3 pt-4 border-t">
          <UButton
            variant="ghost"
            color="neutral"
            @click="goBack"
          >
            {{ t('actions.cancel') }}
          </UButton>
          <UButton
            type="submit"
            :loading="loading"
            :disabled="!selectedPatient"
          >
            {{ t('actions.create') }}
          </UButton>
        </div>
      </form>
    </UCard>
  </div>
</template>
