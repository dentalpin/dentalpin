<script setup lang="ts">
/**
 * PatientHeaderAlertsChips — inline alert chips rendered inside the
 * persistent patient sticky header.
 *
 * Registered into ``patient.header.alerts`` by patients_clinical. The
 * patients module never imports this file — the slot name is the only
 * contract. Surfaces only critical+high severity alerts to keep the
 * header line uncluttered; the full medical history lives in its own
 * smart-card on the Resumen.
 */
import type { PatientExtended, PatientAlert } from '~~/app/types'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()

const patientId = computed(() => props.ctx.patient.id)
const { alerts, getAlertIcon, getSeverityColor } = usePatientAlerts(patientId)

const importantAlerts = computed<PatientAlert[]>(() =>
  alerts.value.filter(a => a.severity === 'critical' || a.severity === 'high')
)
</script>

<template>
  <template
    v-for="alert in importantAlerts"
    :key="`${alert.type}-${alert.title}`"
  >
    <UTooltip
      v-if="alert.details"
      :text="alert.details"
    >
      <UBadge
        :color="getSeverityColor(alert.severity)"
        size="xs"
        variant="subtle"
        class="shrink-0"
      >
        <UIcon
          :name="getAlertIcon(alert.type)"
          class="w-3 h-3 me-1 shrink-0"
        />
        {{ alert.title }}
      </UBadge>
    </UTooltip>
    <UBadge
      v-else
      :color="getSeverityColor(alert.severity)"
      size="xs"
      variant="subtle"
      class="shrink-0"
      :aria-label="t('patients.alerts.label')"
    >
      <UIcon
        :name="getAlertIcon(alert.type)"
        class="w-3 h-3 me-1 shrink-0"
      />
      {{ alert.title }}
    </UBadge>
  </template>
</template>
