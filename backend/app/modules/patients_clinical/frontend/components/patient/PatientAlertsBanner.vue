<script setup lang="ts">
import type { PatientAlert } from '~~/app/types'

interface Props {
  alerts: PatientAlert[]
  compact?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  compact: false
})

const { t } = useI18n()

function getAlertIcon(type: PatientAlert['type']): string {
  const icons: Record<PatientAlert['type'], string> = {
    allergy: 'i-lucide-alert-triangle',
    pregnancy: 'i-lucide-baby',
    lactating: 'i-lucide-heart',
    anticoagulant: 'i-lucide-droplet',
    anesthesia_reaction: 'i-lucide-syringe',
    systemic_disease: 'i-lucide-activity'
  }
  return icons[type] || 'i-lucide-alert-circle'
}

type AlertRole = 'danger' | 'warning' | 'info'

function getBadgeColor(severity: PatientAlert['severity']) {
  switch (severity) {
    case 'critical': return 'error'
    case 'high': return 'warning'
    case 'medium': return 'info'
    case 'low': return 'neutral'
    default: return 'neutral'
  }
}

const criticalAlerts = computed(() =>
  props.alerts.filter(a => a.severity === 'critical' || a.severity === 'high')
)

// Banner role — danger if any critical alerts, otherwise warning
const bannerRole = computed<AlertRole>(() =>
  criticalAlerts.value.length > 0 ? 'danger' : 'warning'
)

const hasCritical = computed(() => criticalAlerts.value.length > 0)

const showExpanded = ref(false)
</script>

<template>
  <div
    v-if="alerts.length > 0"
    class="patient-alerts-banner"
  >
    <!-- Compact mode: just badges -->
    <div
      v-if="compact"
      class="flex flex-wrap gap-1"
    >
      <UBadge
        v-for="(alert, index) in alerts"
        :key="index"
        :color="getBadgeColor(alert.severity)"
        size="xs"
        variant="subtle"
      >
        <UIcon
          :name="getAlertIcon(alert.type)"
          class="w-3 h-3 me-1"
        />
        {{ alert.title }}
      </UBadge>
    </div>

    <!-- Full mode: alert surface (soft bg + text + accent rail, DESIGN §7.1) -->
    <div
      v-else
      :class="[
        bannerRole === 'danger' ? 'alert-surface-danger' : 'alert-surface-warning',
        hasCritical ? (bannerRole === 'danger' ? 'alert-critical-danger' : 'alert-critical-warning') : '',
        'rounded-token-lg px-4 py-3'
      ]"
      role="alert"
    >
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-center gap-2">
          <UIcon
            :name="hasCritical ? 'i-lucide-alert-octagon' : 'i-lucide-alert-triangle'"
            class="w-5 h-5 shrink-0"
            :style="{ color: `var(--color-${bannerRole}-accent)` }"
          />
          <span class="text-ui">
            {{ t('patients.alerts.title', { count: alerts.length }) }}
          </span>
        </div>
        <UButton
          v-if="alerts.length > 2"
          variant="ghost"
          color="neutral"
          size="xs"
          :icon="showExpanded ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
          :aria-label="showExpanded ? t('common.collapse', 'Contraer') : t('common.expand', 'Expandir')"
          @click="showExpanded = !showExpanded"
        />
      </div>

      <div class="mt-2 flex flex-wrap gap-2">
        <template
          v-for="(alert, index) in (showExpanded ? alerts : alerts.slice(0, 3))"
          :key="index"
        >
          <UTooltip
            v-if="alert.details"
            :text="alert.details"
          >
            <UBadge
              :color="getBadgeColor(alert.severity)"
              size="sm"
              variant="subtle"
            >
              <UIcon
                :name="getAlertIcon(alert.type)"
                class="w-3.5 h-3.5 me-1"
              />
              {{ alert.title }}
            </UBadge>
          </UTooltip>
          <UBadge
            v-else
            :color="getBadgeColor(alert.severity)"
            size="sm"
            variant="subtle"
          >
            <UIcon
              :name="getAlertIcon(alert.type)"
              class="w-3.5 h-3.5 me-1"
            />
            {{ alert.title }}
          </UBadge>
        </template>
        <span
          v-if="!showExpanded && alerts.length > 3"
          class="text-caption text-muted self-center"
        >
          +{{ alerts.length - 3 }} {{ t('common.more') }}
        </span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.patient-alerts-banner {
  width: 100%;
}
</style>
