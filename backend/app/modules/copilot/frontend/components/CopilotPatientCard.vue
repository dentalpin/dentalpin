<script setup lang="ts">
export interface PatientResult {
  id: string
  full_name: string
  phone?: string | null
  email?: string | null
  status?: string
  date_of_birth?: string | null
}

const props = defineProps<{ patient: PatientResult }>()
const { t } = useI18n()

const statusColor = computed<'success' | 'neutral'>(() =>
  props.patient.status === 'active' ? 'success' : 'neutral'
)
const statusLabel = computed(() =>
  props.patient.status ? t(`copilot.patientStatus.${props.patient.status}`) : ''
)
</script>

<template>
  <div class="flex items-center gap-3 rounded-lg border border-default bg-elevated p-3">
    <UAvatar
      :alt="patient.full_name"
      size="md"
    />
    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <span class="truncate text-sm font-medium">{{ patient.full_name }}</span>
        <UBadge
          v-if="statusLabel"
          :color="statusColor"
          variant="subtle"
          size="sm"
        >
          {{ statusLabel }}
        </UBadge>
      </div>
      <p
        v-if="patient.phone || patient.email"
        class="truncate text-xs text-muted"
      >
        <template v-if="patient.phone">
          {{ patient.phone }}
        </template>
        <template v-if="patient.phone && patient.email">
          ·
        </template>
        <template v-if="patient.email">
          {{ patient.email }}
        </template>
      </p>
    </div>
    <UButton
      icon="i-lucide-user"
      color="neutral"
      variant="soft"
      size="xs"
      :to="`/patients/${patient.id}`"
    >
      {{ t('copilot.card.viewPatient') }}
    </UButton>
  </div>
</template>
