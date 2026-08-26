<script setup lang="ts">
import type { Surface, ToothTreatmentView, TreatmentStatus } from '~~/app/types'
import { getTreatmentColor, isSurfaceTreatment, getAllowedStatusesForTreatment } from '~~/app/config/odontogramConstants'
import type { UiColor } from '~~/app/config/severity'
import { getTreatmentDisplayName } from '~~/app/utils/treatmentView'

const props = defineProps<{
  /** Per-tooth view over a Treatment (see utils/treatmentView.ts). */
  treatment: ToothTreatmentView | null
  open: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'update': [treatmentId: string, data: { status?: TreatmentStatus, notes?: string }]
  'delete': [treatmentId: string]
  'perform': [treatmentId: string]
}>()

const { t, locale } = useI18n()

// Local state
const status = ref<TreatmentStatus>('existing')
const selectedSurfaces = ref<Surface[]>([])
const notes = ref('')

// All surfaces
const allSurfaces: Surface[] = ['M', 'D', 'O', 'V', 'L']

// Is surface treatment
const isSurfaceType = computed(() => {
  if (!props.treatment) return false
  return isSurfaceTreatment(props.treatment.treatment_type)
})

// Sync local state with treatment prop
watch(() => props.treatment, (treatment) => {
  if (treatment) {
    status.value = treatment.status
    selectedSurfaces.value = [...(treatment.surfaces || [])]
    notes.value = treatment.notes || ''
  }
}, { immediate: true })

// Treatment label
const treatmentLabel = computed(() => {
  if (!props.treatment) return ''
  return getTreatmentDisplayName(props.treatment, locale.value, t)
})

// Treatment color
const treatmentColor = computed(() => {
  if (!props.treatment) return '#9CA3AF'
  return getTreatmentColor(props.treatment.treatment_type)
})

// All status options
const allStatusOptions: { value: TreatmentStatus, label: () => string, color: UiColor }[] = [
  { value: 'existing', label: () => t('odontogram.status.existing'), color: 'neutral' },
  { value: 'planned', label: () => t('odontogram.status.planned'), color: 'warning' }
]

// Status options filtered by treatment type
const statusOptions = computed(() => {
  if (!props.treatment) return allStatusOptions.map(o => ({ ...o, label: o.label() }))

  const allowedStatuses = getAllowedStatusesForTreatment(props.treatment.treatment_type)
  return allStatusOptions
    .filter(opt => allowedStatuses.includes(opt.value))
    .map(o => ({ ...o, label: o.label() }))
})

function toggleSurface(surface: Surface) {
  const index = selectedSurfaces.value.indexOf(surface)
  if (index === -1) {
    selectedSurfaces.value.push(surface)
  } else {
    selectedSurfaces.value.splice(index, 1)
  }
}

function handleSave() {
  if (!props.treatment) return

  const data: { status?: TreatmentStatus, notes?: string } = {}

  if (status.value !== props.treatment.status) {
    data.status = status.value
  }

  if (notes.value !== (props.treatment.notes || '')) {
    data.notes = notes.value
  }

  if (Object.keys(data).length > 0) {
    emit('update', props.treatment.treatment_id, data)
  } else {
    emit('update:open', false)
  }
}

function handleDelete() {
  if (!props.treatment) return
  emit('delete', props.treatment.treatment_id)
}

function handleMarkPerformed() {
  if (!props.treatment) return
  emit('perform', props.treatment.treatment_id)
}

function handleClose() {
  emit('update:open', false)
}
</script>

<template>
  <UModal
    :open="open"
    @update:open="handleClose"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <span
                class="w-4 h-4 rounded-full flex-shrink-0"
                :style="{ backgroundColor: treatmentColor }"
              />
              <span class="font-semibold text-default">{{ treatmentLabel }}</span>
              <UBadge
                v-if="treatment"
                :color="status === 'planned' ? 'warning' : 'neutral'"
                variant="subtle"
                size="xs"
              >
                {{ t('odontogram.tooth') }} {{ treatment.tooth_number }}
              </UBadge>
            </div>
            <UButton
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              color="neutral"
              variant="ghost"
              size="sm"
              @click="handleClose"
            />
          </div>
        </template>

        <div
          v-if="treatment"
          class="space-y-6"
        >
          <!-- Status selection -->
          <div>
            <label class="block text-sm font-medium mb-2 text-muted">
              {{ t('odontogram.treatments.selectStatus') }}
            </label>
            <div class="flex gap-2">
              <UButton
                v-for="option in statusOptions"
                :key="option.value"
                :color="status === option.value ? option.color : 'neutral'"
                :variant="status === option.value ? 'solid' : 'outline'"
                size="sm"
                @click="status = option.value"
              >
                {{ option.label }}
              </UButton>
            </div>
          </div>

          <!-- Surface selection (only for surface treatments) -->
          <div v-if="isSurfaceType">
            <label class="block text-sm font-medium mb-2 text-muted">
              {{ t('odontogram.selectSurfaces') }}
            </label>
            <div class="flex gap-2 flex-wrap">
              <UButton
                v-for="surface in allSurfaces"
                :key="surface"
                :color="selectedSurfaces.includes(surface) ? 'primary' : 'neutral'"
                :variant="selectedSurfaces.includes(surface) ? 'solid' : 'outline'"
                size="sm"
                @click="toggleSurface(surface)"
              >
                {{ surface }} - {{ t(`odontogram.surfaces.${surface}`) }}
              </UButton>
            </div>
            <p
              v-if="selectedSurfaces.length > 0"
              class="text-caption text-subtle mt-2"
            >
              {{ selectedSurfaces.length }} {{ t('odontogram.surfacesSelected') }}
            </p>
          </div>

          <!-- Notes -->
          <div>
            <label class="block text-sm font-medium mb-2 text-muted">
              {{ t('patients.notes') }}
            </label>
            <UTextarea
              v-model="notes"
              :placeholder="t('patients.notes')"
              :rows="3"
            />
          </div>

          <!-- Quick action: Mark as performed -->
          <div
            v-if="treatment.status === 'planned'"
            class="pt-4 border-t border-default"
          >
            <UButton
              color="success"
              variant="soft"
              block
              icon="i-lucide-check"
              @click="handleMarkPerformed"
            >
              {{ t('odontogram.treatments.markPerformed') }}
            </UButton>
          </div>
        </div>

        <template #footer>
          <div class="flex justify-between w-full">
            <UButton
              color="error"
              variant="ghost"
              icon="i-lucide-trash-2"
              @click="handleDelete"
            >
              {{ t('common.delete') }}
            </UButton>
            <div class="flex gap-2">
              <UButton
                color="neutral"
                variant="outline"
                @click="handleClose"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="primary"
                @click="handleSave"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
