<script setup lang="ts">
import type { PatientExtended } from '~~/app/types'
import { computeAge, formatPatientDate } from '../../../utils/medicalSnapshot'

interface Props {
  patient: PatientExtended
  canEdit: boolean
}

const props = defineProps<Props>()

const emit = defineEmits<{ edit: [] }>()

const { t, locale } = useI18n()

const age = computed(() => computeAge(props.patient.date_of_birth))

const initials = computed(() => {
  const first = props.patient.first_name?.[0] ?? ''
  const last = props.patient.last_name?.[0] ?? ''
  return (first + last).toUpperCase()
})

const statusColor = computed<'success' | 'neutral'>(() =>
  props.patient.status === 'active' ? 'success' : 'neutral'
)

const birthDisplay = computed(() => {
  const formatted = formatPatientDate(props.patient.date_of_birth, locale.value === 'en' ? 'en-US' : 'es-ES')
  if (!formatted) return null
  if (age.value === null) return formatted
  return t('patients.personalInfo.birthWithAge', { date: formatted, age: age.value })
})

const documentDisplay = computed(() => {
  if (!props.patient.national_id) return null
  const type = props.patient.national_id_type?.toUpperCase() ?? ''
  return type ? `${type}: ${props.patient.national_id}` : props.patient.national_id
})

const genderLabel = computed(() =>
  props.patient.gender ? t(`patients.gender.${props.patient.gender}`) : null
)
</script>

<template>
  <UCard
    role="region"
    aria-labelledby="personal-info-title"
  >
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 min-w-0">
          <UIcon
            name="i-lucide-user"
            class="w-5 h-5 text-default shrink-0"
            aria-hidden="true"
          />
          <h2
            id="personal-info-title"
            class="text-h2 text-default truncate"
          >
            {{ t('patients.personalInfo.title') }}
          </h2>
        </div>
        <UButton
          v-if="canEdit"
          variant="soft"
          color="neutral"
          icon="i-lucide-pencil"
          size="sm"
          :aria-label="t('patients.editDemographics')"
          @click="emit('edit')"
        >
          <span class="hidden lg:inline">{{ t('common.edit') }}</span>
        </UButton>
      </div>
    </template>

    <div class="flex flex-col sm:flex-row sm:items-center gap-4 mb-4 pb-4 border-b border-default">
      <UAvatar
        v-if="patient.photo_url"
        :src="patient.photo_url"
        :alt="`${patient.first_name} ${patient.last_name}`"
        size="lg"
        class="sm:size-2xl"
      />
      <UAvatar
        v-else
        :text="initials"
        size="lg"
      />
      <div class="min-w-0 flex-1">
        <p class="text-h2 text-default break-words">
          {{ patient.first_name }} {{ patient.last_name }}
        </p>
        <div class="flex flex-wrap items-center gap-2 mt-1">
          <span
            v-if="age !== null"
            class="text-caption text-subtle"
          >
            {{ t('patients.personalInfo.ageLabel', { age }) }}
          </span>
          <UBadge
            :color="statusColor"
            variant="subtle"
            size="sm"
          >
            {{ patient.status === 'active' ? t('patients.status.active') : t('patients.status.archived') }}
          </UBadge>
        </div>
      </div>
    </div>

    <dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
      <div class="flex items-start gap-3 py-2">
        <UIcon
          name="i-lucide-cake"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <dt class="text-caption text-subtle">
            {{ t('patients.dateOfBirth') }}
          </dt>
          <dd class="text-body text-default break-words">
            {{ birthDisplay ?? '—' }}
          </dd>
        </div>
      </div>

      <div
        v-if="genderLabel"
        class="flex items-start gap-3 py-2"
      >
        <UIcon
          name="i-lucide-user-2"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <dt class="text-caption text-subtle">
            {{ t('patients.gender.label') }}
          </dt>
          <dd class="text-body text-default break-words">
            {{ genderLabel }}
          </dd>
        </div>
      </div>

      <div
        v-if="documentDisplay"
        class="flex items-start gap-3 py-2"
      >
        <UIcon
          name="i-lucide-id-card"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <dt class="text-caption text-subtle">
            {{ t('patients.nationalId') }}
          </dt>
          <dd class="text-body text-default break-words">
            {{ documentDisplay }}
          </dd>
        </div>
      </div>

      <div
        v-if="patient.profession"
        class="flex items-start gap-3 py-2"
      >
        <UIcon
          name="i-lucide-briefcase"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <dt class="text-caption text-subtle">
            {{ t('patients.profession') }}
          </dt>
          <dd class="text-body text-default break-words">
            {{ patient.profession }}
          </dd>
        </div>
      </div>

      <div
        v-if="patient.workplace"
        class="flex items-start gap-3 py-2"
      >
        <UIcon
          name="i-lucide-building-2"
          class="w-4 h-4 text-subtle shrink-0 mt-1"
          aria-hidden="true"
        />
        <div class="min-w-0">
          <dt class="text-caption text-subtle">
            {{ t('patients.workplace') }}
          </dt>
          <dd class="text-body text-default break-words">
            {{ patient.workplace }}
          </dd>
        </div>
      </div>
    </dl>

    <div
      v-if="patient.notes"
      class="mt-4 pt-4 border-t border-default"
    >
      <dt class="text-caption text-subtle mb-1">
        {{ t('patients.notes') }}
      </dt>
      <dd class="text-body text-default whitespace-pre-wrap break-words">
        {{ patient.notes }}
      </dd>
    </div>
  </UCard>
</template>
