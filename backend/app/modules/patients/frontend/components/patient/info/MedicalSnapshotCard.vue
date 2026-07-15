<script setup lang="ts">
import type { AllergyEntry, MedicalHistory, PatientAlert } from '~~/app/types'
import {
  buildConditionChips,
  buildMedicationItems,
  diseaseColor,
  formatPatientDate,
  hasAnyMedicalData,
  hasCriticalAlert,
  severityColor,
  severityIcon,
  severityVariant,
} from '../../../utils/medicalSnapshot'

interface Props {
  medicalHistory: MedicalHistory | null
  activeAlerts?: PatientAlert[]
  canEdit: boolean
}

const props = withDefaults(defineProps<Props>(), {
  activeAlerts: () => [],
})

const emit = defineEmits<{
  edit: []
  completeHistory: []
}>()

const { t } = useI18n()

const hasData = computed(() => hasAnyMedicalData(props.medicalHistory))
const isExplicitlyReviewed = computed(() => Boolean(props.medicalHistory?.last_updated_at))
const allergies = computed<AllergyEntry[]>(() => props.medicalHistory?.allergies ?? [])
const diseases = computed(() => props.medicalHistory?.systemic_diseases ?? [])
const medications = computed(() => buildMedicationItems(props.medicalHistory))
const conditionChips = computed(() => buildConditionChips(props.medicalHistory, t))
const showCriticalBorder = computed(() => hasCriticalAlert(props.activeAlerts))

const reviewedDate = computed(() =>
  props.medicalHistory?.last_updated_at
    ? formatPatientDate(props.medicalHistory.last_updated_at)
    : null,
)

function allergyTooltip(a: AllergyEntry): string {
  const parts: string[] = []
  if (a.reaction) parts.push(a.reaction)
  if (a.notes) parts.push(a.notes)
  return parts.join(' · ')
}
</script>

<template>
  <UCard
    :class="showCriticalBorder ? 'border-l-4 border-(--color-danger-accent)' : ''"
    role="region"
    aria-labelledby="medical-snapshot-title"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 min-w-0">
          <UIcon
            name="i-lucide-heart-pulse"
            class="w-5 h-5 text-default shrink-0"
            aria-hidden="true"
          />
          <h2
            id="medical-snapshot-title"
            class="text-h2 text-default truncate"
          >
            {{ t('patients.medicalSnapshot.title') }}
          </h2>
        </div>
        <UButton
          v-if="canEdit"
          variant="soft"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editMedicalHistory')"
          @click="emit('edit')"
        >
          <span class="hidden lg:inline">{{ t('common.edit') }}</span>
        </UButton>
      </div>
    </template>

    <!-- Allergies block — three states -->
    <section
      class="mb-4"
      :aria-label="t('patients.medicalSnapshot.allergiesLabel')"
    >
      <!-- A. No medical data at all -->
      <div
        v-if="!hasData"
        class="alert-surface-warning rounded-token-md px-3 py-3 flex flex-wrap items-center gap-2"
        role="status"
      >
        <UIcon
          name="i-lucide-alert-circle"
          class="w-4 h-4"
          :style="{ color: 'var(--color-warning-accent)' }"
          aria-hidden="true"
        />
        <span class="text-body">
          {{ t('patients.medicalSnapshot.allergiesNotReviewed') }}
        </span>
        <UButton
          v-if="canEdit"
          variant="link"
          color="warning"
          size="sm"
          class="ml-auto"
          @click="emit('completeHistory')"
        >
          {{ t('patients.medicalSnapshot.completeHistory') }} →
        </UButton>
      </div>

      <!-- B. No allergies (history has other data, or explicitly reviewed) -->
      <div
        v-else-if="allergies.length === 0"
        class="alert-surface-success rounded-token-md px-3 py-3 flex flex-wrap items-center gap-2"
        role="status"
      >
        <UIcon
          name="i-lucide-shield-check"
          class="w-4 h-4"
          :style="{ color: 'var(--color-success-accent)' }"
          aria-hidden="true"
        />
        <span class="text-body">{{ t('patients.medicalSnapshot.allergiesEmpty') }}</span>
        <span
          v-if="isExplicitlyReviewed && reviewedDate"
          class="text-caption text-subtle ml-auto"
        >
          {{ t('patients.medicalSnapshot.reviewedOn', { date: reviewedDate }) }}
        </span>
      </div>

      <!-- C. List of allergies -->
      <div
        v-else
        class="flex flex-wrap gap-2"
      >
        <template
          v-for="a in allergies"
          :key="a.name"
        >
          <UTooltip
            v-if="allergyTooltip(a)"
            :text="allergyTooltip(a)"
          >
            <UBadge
              :color="severityColor(a.severity)"
              :variant="severityVariant(a.severity)"
              size="md"
              class="max-w-full"
            >
              <UIcon
                :name="severityIcon(a.severity)"
                class="w-3.5 h-3.5 mr-1.5 shrink-0"
                aria-hidden="true"
              />
              <span class="break-words">{{ a.name }} · {{ t(`patients.medicalHistory.severity.${a.severity}`) }}</span>
            </UBadge>
          </UTooltip>
          <UBadge
            v-else
            :color="severityColor(a.severity)"
            :variant="severityVariant(a.severity)"
            size="md"
            class="max-w-full"
          >
            <UIcon
              :name="severityIcon(a.severity)"
              class="w-3.5 h-3.5 mr-1.5 shrink-0"
              aria-hidden="true"
            />
            <span class="break-words">{{ a.name }} · {{ t(`patients.medicalHistory.severity.${a.severity}`) }}</span>
          </UBadge>
        </template>
      </div>
    </section>

    <!-- 3-col grid: chronic / medications / conditions -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 lg:gap-6">
      <!-- Chronic / systemic diseases -->
      <section>
        <h3 class="text-caption uppercase tracking-wide text-subtle flex items-center gap-1.5">
          <UIcon
            name="i-lucide-activity"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.medicalHistory.systemicDiseases') }}
        </h3>
        <div
          v-if="diseases.length"
          class="flex flex-wrap gap-1.5 mt-2"
        >
          <UBadge
            v-for="d in diseases"
            :key="d.name"
            :color="diseaseColor(d)"
            variant="subtle"
            size="md"
            class="max-w-full"
          >
            <span class="break-words">{{ d.name }}</span>
          </UBadge>
        </div>
        <p
          v-else
          class="text-body text-subtle mt-2"
        >
          —
        </p>
      </section>

      <!-- Medications -->
      <section>
        <h3 class="text-caption uppercase tracking-wide text-subtle flex items-center gap-1.5">
          <UIcon
            name="i-lucide-pill"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.medicalHistory.medications') }}
        </h3>
        <ul
          v-if="medications.length"
          class="space-y-2 mt-2"
        >
          <li
            v-for="m in medications"
            :key="m.name"
            :class="m.highlight ? 'border-l-2 border-(--color-warning-accent) pl-2' : ''"
          >
            <span class="text-body text-default break-words">{{ m.name }}</span>
            <span
              v-if="m.detail"
              class="text-caption text-subtle block break-words"
            >{{ m.detail }}</span>
          </li>
        </ul>
        <p
          v-else
          class="text-body text-subtle mt-2"
        >
          —
        </p>
      </section>

      <!-- Special conditions -->
      <section>
        <h3 class="text-caption uppercase tracking-wide text-subtle flex items-center gap-1.5">
          <UIcon
            name="i-lucide-clipboard-list"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.medicalHistory.specialConditions') }}
        </h3>
        <div
          v-if="conditionChips.length"
          class="flex flex-wrap gap-1.5 mt-2"
        >
          <UBadge
            v-for="c in conditionChips"
            :key="c.key"
            :color="c.color"
            variant="subtle"
            size="md"
            class="max-w-full"
          >
            <UIcon
              :name="c.icon"
              class="w-3.5 h-3.5 mr-1.5 shrink-0"
              aria-hidden="true"
            />
            <span class="break-words">{{ c.label }}</span>
          </UBadge>
        </div>
        <p
          v-else
          class="text-body text-subtle mt-2"
        >
          —
        </p>
      </section>
    </div>
  </UCard>
</template>
