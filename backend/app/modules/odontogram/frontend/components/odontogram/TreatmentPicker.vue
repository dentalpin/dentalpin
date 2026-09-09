<script setup lang="ts">
import type { Surface, TreatmentStatus, TreatmentType } from '~~/app/types'
import { TREATMENT_COLORS } from './ToothSVGPaths'

const _props = defineProps<{
  toothNumber: number
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'select': [data: {
    treatment_type: TreatmentType
    status: TreatmentStatus
    surfaces?: Surface[]
    notes?: string
  }]
}>()

const { t } = useI18n()

// Form state
const selectedType = ref<TreatmentType | null>(null)
const selectedStatus = ref<TreatmentStatus>('existing')
const selectedSurfaces = ref<Surface[]>([])
const notes = ref('')

// Treatment categories for organized display
const treatmentCategories = computed(() => [
  {
    key: 'common',
    label: t('odontogram.treatments.categories.common'),
    treatments: [
      { key: 'filling' as TreatmentType, label: t('odontogram.treatments.types.filling'), category: 'surface' },
      { key: 'crown' as TreatmentType, label: t('odontogram.treatments.types.crown'), category: 'whole_tooth' },
      { key: 'root_canal' as TreatmentType, label: t('odontogram.treatments.types.root_canal'), category: 'whole_tooth' },
      { key: 'extraction' as TreatmentType, label: t('odontogram.treatments.types.extraction'), category: 'whole_tooth' },
      { key: 'implant' as TreatmentType, label: t('odontogram.treatments.types.implant'), category: 'whole_tooth' }
    ]
  },
  {
    key: 'restorative',
    label: t('odontogram.treatments.categories.restorative'),
    treatments: [
      { key: 'veneer' as TreatmentType, label: t('odontogram.treatments.types.veneer'), category: 'whole_tooth' },
      { key: 'post' as TreatmentType, label: t('odontogram.treatments.types.post'), category: 'whole_tooth' },
      { key: 'crown_on_implant' as TreatmentType, label: t('odontogram.treatments.types.crown_on_implant'), category: 'whole_tooth' },
      { key: 'provisional_crown_on_implant' as TreatmentType, label: t('odontogram.treatments.types.provisional_crown_on_implant'), category: 'whole_tooth' },
      { key: 'bridge_pontic' as TreatmentType, label: t('odontogram.treatments.types.bridge_pontic'), category: 'whole_tooth' },
      { key: 'bridge_abutment' as TreatmentType, label: t('odontogram.treatments.types.bridge_abutment'), category: 'whole_tooth' }
    ]
  },
  {
    key: 'other',
    label: t('odontogram.treatments.categories.other'),
    treatments: [
      { key: 'caries' as TreatmentType, label: t('odontogram.treatments.types.caries'), category: 'surface' },
      { key: 'sealant' as TreatmentType, label: t('odontogram.treatments.types.sealant'), category: 'surface' },
      { key: 'fracture' as TreatmentType, label: t('odontogram.treatments.types.fracture'), category: 'whole_tooth' },
      { key: 'missing' as TreatmentType, label: t('odontogram.treatments.types.missing'), category: 'whole_tooth' },
      { key: 'apicoectomy' as TreatmentType, label: t('odontogram.treatments.types.apicoectomy'), category: 'whole_tooth' }
    ]
  }
])

const surfaces: Surface[] = ['M', 'D', 'O', 'V', 'L']

// Get selected treatment info
const selectedTreatmentInfo = computed(() => {
  if (!selectedType.value) return null
  for (const category of treatmentCategories.value) {
    const found = category.treatments.find(t => t.key === selectedType.value)
    if (found) return found
  }
  return null
})

const isSurfaceTreatment = computed(() => {
  return selectedTreatmentInfo.value?.category === 'surface'
})

// Status options
const statusOptions = [
  { value: 'existing' as TreatmentStatus, label: t('odontogram.status.existing'), color: 'neutral', icon: 'i-lucide-check-circle' },
  { value: 'planned' as TreatmentStatus, label: t('odontogram.status.planned'), color: 'warning', icon: 'i-lucide-clock' }
]

function getTreatmentColor(type: TreatmentType): string {
  return TREATMENT_COLORS[type] || '#9CA3AF'
}

function toggleSurface(surface: Surface) {
  const index = selectedSurfaces.value.indexOf(surface)
  if (index >= 0) {
    selectedSurfaces.value.splice(index, 1)
  } else {
    selectedSurfaces.value.push(surface)
  }
}

function handleSubmit() {
  if (!selectedType.value) return

  const data: {
    treatment_type: TreatmentType
    status: TreatmentStatus
    surfaces?: Surface[]
    notes?: string
  } = {
    treatment_type: selectedType.value,
    status: selectedStatus.value
  }

  if (isSurfaceTreatment.value && selectedSurfaces.value.length > 0) {
    data.surfaces = [...selectedSurfaces.value]
  }

  if (notes.value.trim()) {
    data.notes = notes.value.trim()
  }

  emit('select', data)
  resetForm()
  emit('update:open', false)
}

function resetForm() {
  selectedType.value = null
  selectedStatus.value = 'existing'
  selectedSurfaces.value = []
  notes.value = ''
}

function handleClose() {
  resetForm()
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="handleClose"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-plus-circle"
          class="w-5 h-5 text-primary-accent"
        />
        <span>{{ t('odontogram.treatments.addTreatment') }}</span>
        <UBadge
          color="neutral"
          variant="subtle"
        >
          {{ t('odontogram.tooth') }} {{ toothNumber }}
        </UBadge>
      </div>
    </template>

    <template #body>
      <div class="space-y-4">
        <!-- Treatment Type Selection -->
        <div>
          <label class="block text-sm font-medium mb-2">
            {{ t('appointments.treatmentType') }}
          </label>
          <div class="space-y-3">
            <div
              v-for="category in treatmentCategories"
              :key="category.key"
            >
              <div class="text-caption text-subtle mb-1.5">
                {{ category.label }}
              </div>
              <div class="flex flex-wrap gap-1.5">
                <button
                  v-for="treatment in category.treatments"
                  :key="treatment.key"
                  type="button"
                  class="treatment-type-btn"
                  :class="{ selected: selectedType === treatment.key }"
                  @click="selectedType = treatment.key"
                >
                  <span
                    class="w-2.5 h-2.5 rounded-full me-1.5"
                    :style="{ backgroundColor: getTreatmentColor(treatment.key) }"
                  />
                  {{ treatment.label }}
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Status Selection -->
        <div>
          <label class="block text-sm font-medium mb-2">
            {{ t('odontogram.treatments.selectStatus') }}
          </label>
          <div class="flex gap-2">
            <button
              v-for="option in statusOptions"
              :key="option.value"
              type="button"
              class="status-btn"
              :class="{ selected: selectedStatus === option.value, [option.color]: true }"
              @click="selectedStatus = option.value"
            >
              <UIcon
                :name="option.icon"
                class="w-4 h-4 me-1"
              />
              {{ option.label }}
            </button>
          </div>
        </div>

        <!-- Surface Selection (only for surface treatments) -->
        <div v-if="isSurfaceTreatment">
          <label class="block text-sm font-medium mb-2">
            {{ t('odontogram.surfaces.M') }} / {{ t('odontogram.surfaces.D') }} / ...
          </label>
          <div class="flex gap-2">
            <button
              v-for="surface in surfaces"
              :key="surface"
              type="button"
              class="surface-btn"
              :class="{ selected: selectedSurfaces.includes(surface) }"
              @click="toggleSurface(surface)"
            >
              {{ surface }}
            </button>
          </div>
          <p class="text-caption text-subtle mt-1">
            {{ t(`odontogram.surfaces.${selectedSurfaces[0]}`, '') }}
            <span v-if="selectedSurfaces.length > 1">
              + {{ selectedSurfaces.length - 1 }}
            </span>
          </p>
        </div>

        <!-- Notes -->
        <UFormField :label="t('patients.notes')">
          <UTextarea
            v-model="notes"
            :placeholder="t('patients.notes')"
            :rows="2"
          />
        </UFormField>
      </div>
    </template>

    <template #footer>
      <div class="flex justify-end gap-2">
        <UButton
          color="neutral"
          variant="ghost"
          @click="handleClose"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          color="primary"
          :disabled="!selectedType"
          @click="handleSubmit"
        >
          {{ t('common.save') }}
        </UButton>
      </div>
    </template>
  </UModal>
</template>

<style scoped>
.treatment-type-btn {
  padding: 0.375rem 0.625rem;
  font-size: 0.875rem;
  border-radius: 0.375rem;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  transition: all 0.15s;
}

:root.dark .treatment-type-btn {
  border-color: #374151;
}

.treatment-type-btn:hover {
  border-color: #93c5fd;
  background-color: #eff6ff;
}

:root.dark .treatment-type-btn:hover {
  background-color: rgba(59, 130, 246, 0.2);
}

.treatment-type-btn.selected {
  border-color: #3b82f6;
  background-color: #eff6ff;
  box-shadow: 0 0 0 1px #3b82f6;
}

:root.dark .treatment-type-btn.selected {
  background-color: rgba(59, 130, 246, 0.3);
}

.status-btn {
  padding: 0.5rem 0.75rem;
  font-size: 0.875rem;
  border-radius: 0.375rem;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  transition: all 0.15s;
  flex: 1;
  justify-content: center;
}

:root.dark .status-btn {
  border-color: #374151;
}

.status-btn.selected.success {
  border-color: #22c55e;
  background-color: #f0fdf4;
  color: #15803d;
}

:root.dark .status-btn.selected.success {
  background-color: rgba(34, 197, 94, 0.3);
}

.status-btn.selected.warning {
  border-color: #f59e0b;
  background-color: #fffbeb;
  color: #b45309;
}

:root.dark .status-btn.selected.warning {
  background-color: rgba(245, 158, 11, 0.3);
}

.status-btn.selected.neutral {
  border-color: #9ca3af;
  background-color: #f3f4f6;
  color: #374151;
}

:root.dark .status-btn.selected.neutral {
  background-color: #1f2937;
}

.surface-btn {
  width: 2.5rem;
  height: 2.5rem;
  font-size: 0.875rem;
  font-weight: 500;
  border-radius: 0.375rem;
  border: 1px solid #e5e7eb;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

:root.dark .surface-btn {
  border-color: #374151;
}

.surface-btn:hover {
  border-color: #93c5fd;
  background-color: #eff6ff;
}

.surface-btn.selected {
  border-color: #3b82f6;
  background-color: #dbeafe;
  color: #1d4ed8;
}

:root.dark .surface-btn.selected {
  background-color: rgba(59, 130, 246, 0.3);
}
</style>
