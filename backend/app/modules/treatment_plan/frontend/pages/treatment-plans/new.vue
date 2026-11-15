<script setup lang="ts">
import type { Patient, Surface } from '~~/app/types'

const router = useRouter()
const { t } = useI18n()
const { locale } = useI18n()
const { createPlanBatch, loading } = useTreatmentPlans()
const { professionals, fetchProfessionals } = useProfessionals()
const treatmentCatalog = useTreatmentCatalog()
const api = useApi()

interface ProposalLine {
  catalog_item_id: string | undefined
  tooth_numbers: string
  surfaces: string
  notes: string
}

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
const proposalLines = ref<ProposalLine[]>([
  { catalog_item_id: undefined, tooth_numbers: '', surfaces: '', notes: '' }
])

// Fetch professionals on mount
onMounted(() => {
  fetchProfessionals()
  treatmentCatalog.fetchTreatments()
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

const procedureOptions = computed(() => treatmentCatalog.treatments.value
  .filter(item => !!item.odontogram_treatment_type)
  .map(item => ({
    label: item.names[locale.value] || item.names.es || item.names.en || item.internal_code,
    value: item.id
  })))

function addProposalLine() {
  proposalLines.value.push({
    catalog_item_id: undefined,
    tooth_numbers: '',
    surfaces: '',
    notes: ''
  })
}

function removeProposalLine(index: number) {
  if (proposalLines.value.length > 1) proposalLines.value.splice(index, 1)
}

function parseNumbers(value: string): number[] {
  return value.split(/[\s,;]+/).filter(Boolean).map(Number)
}

function lineIsValid(line: ProposalLine): boolean {
  const teeth = parseNumbers(line.tooth_numbers)
  return !!line.catalog_item_id
    && teeth.length > 0
    && teeth.every(Number.isInteger)
    && surfacesAreValid(line)
}

function surfacesAreValid(line: ProposalLine): boolean {
  const surfaces = line.surfaces.split(/[\s,;]+/).filter(Boolean)
  return surfaces.every(surface => ['M', 'D', 'O', 'V', 'L'].includes(surface))
}

async function handleSubmit() {
  if (!selectedPatient.value || !proposalLines.value.every(lineIsValid)) return

  const plan = await createPlanBatch({
    plan: {
      patient_id: selectedPatient.value.id,
      title: form.value.title || undefined,
      assigned_professional_id: form.value.assigned_professional_id || undefined,
      diagnosis_notes: form.value.diagnosis_notes || undefined,
      internal_notes: form.value.internal_notes || undefined
    },
    items: proposalLines.value.map((line) => {
      const teeth = parseNumbers(line.tooth_numbers)
      const surfaces = line.surfaces
        .split(/[\s,;]+/)
        .filter((surface): surface is Surface => ['M', 'D', 'O', 'V', 'L'].includes(surface))
      return {
        create_treatment: {
          catalog_item_id: line.catalog_item_id,
          tooth_numbers: teeth,
          surfaces: surfaces.length ? surfaces : undefined,
          status: 'planned' as const,
          notes: line.notes || undefined
        }
      }
    })
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
                <span dir="ltr">{{ selectedPatient.phone }}</span>
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
                class="w-full px-4 py-2 text-start hover:bg-surface-muted"
                @click="selectPatient(patient)"
              >
                <p class="font-medium">
                  {{ patient.last_name }}, {{ patient.first_name }}
                </p>
                <p class="text-caption text-subtle">
                  <span dir="ltr">{{ patient.phone }}</span>
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

        <section class="space-y-4 border-t border-default pt-5">
          <div class="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 class="text-lg font-semibold text-default">
                {{ t('treatmentPlans.batch.title', 'Диагнозы и процедуры') }}
              </h2>
              <p class="text-sm text-muted">
                {{ t('treatmentPlans.batch.description', 'Выберите процедуру из каталога и укажите зубы. Врач проверит весь план и смету перед подтверждением.') }}
              </p>
            </div>
            <UButton
              type="button"
              variant="soft"
              icon="i-lucide-plus"
              :disabled="proposalLines.length >= 100"
              @click="addProposalLine"
            >
              {{ t('treatmentPlans.batch.addLine', 'Добавить строку') }}
            </UButton>
          </div>

          <UAlert
            v-if="!treatmentCatalog.loading.value && procedureOptions.length === 0"
            icon="i-lucide-book-open-check"
            color="warning"
            variant="subtle"
            :title="t('treatmentPlans.batch.emptyCatalog', 'В каталоге нет процедур для одонтограммы')"
            :description="t('treatmentPlans.batch.emptyCatalogHint', 'Сначала добавьте и сопоставьте процедуры в настройках каталога.')"
          />

          <div
            v-for="(line, index) in proposalLines"
            :key="index"
            class="grid gap-3 rounded-lg border border-default bg-surface-muted/40 p-4 sm:grid-cols-2"
          >
            <UFormField
              :label="t('treatmentPlans.batch.procedure', 'Процедура каталога')"
              required
            >
              <USelect
                v-model="line.catalog_item_id"
                :items="procedureOptions"
                value-key="value"
                :placeholder="t('treatmentPlans.batch.selectProcedure', 'Выберите процедуру')"
                :disabled="treatmentCatalog.loading.value || procedureOptions.length === 0"
              />
            </UFormField>
            <UFormField
              :label="t('treatmentPlans.batch.teeth', 'Номера зубов (FDI)')"
              required
            >
              <UInput
                v-model="line.tooth_numbers"
                placeholder="14, 15, 26"
                inputmode="numeric"
              />
            </UFormField>
            <UFormField :label="t('treatmentPlans.batch.surfaces', 'Поверхности (необязательно)')">
              <UInput
                v-model="line.surfaces"
                placeholder="M, O, D"
              />
              <p
                v-if="!surfacesAreValid(line)"
                class="mt-1 text-xs text-error"
              >
                {{ t('treatmentPlans.batch.invalidSurfaces', 'Допустимы поверхности: M, D, O, V, L.') }}
              </p>
            </UFormField>
            <UFormField :label="t('treatmentPlans.batch.notes', 'Комментарий к строке')">
              <UInput v-model="line.notes" />
            </UFormField>
            <div class="flex items-center justify-between gap-3 sm:col-span-2">
              <span class="text-xs text-muted">{{ t('treatmentPlans.batch.groupingHint', 'Зубы одной строки будут сгруппированы в одном пункте плана.') }}</span>
              <UButton
                v-if="proposalLines.length > 1"
                type="button"
                variant="ghost"
                color="error"
                icon="i-lucide-trash-2"
                :aria-label="t('common.delete')"
                @click="removeProposalLine(index)"
              />
            </div>
          </div>
        </section>

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
            :disabled="!selectedPatient || !proposalLines.length || !proposalLines.every(lineIsValid) || procedureOptions.length === 0"
          >
            {{ t('treatmentPlans.batch.createForReview', 'Создать план на проверку врача') }}
          </UButton>
        </div>
      </form>
    </UCard>
  </div>
</template>
