<script setup lang="ts">
import type { Appointment } from '~~/app/types'
import { formatPatientDate, nextAppointmentProximity } from '../../../utils/medicalSnapshot'

interface Props {
  lastVisit: Appointment | null
  nextAppointment: Appointment | null
}

const props = defineProps<Props>()

const { t, locale } = useI18n()

function appointmentDate(a: Appointment): string | null {
  return formatPatientDate(a.start_time, locale.value === 'en' ? 'en-US' : 'es-ES')
}

function appointmentTime(a: Appointment): string | null {
  if (!a.start_time) return null
  const d = new Date(a.start_time)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleTimeString(locale.value === 'en' ? 'en-US' : 'es-ES', {
    hour: '2-digit',
    minute: '2-digit'
  })
}

function appointmentTreatment(a: Appointment): string | null {
  if (a.treatments?.length) return a.treatments[0]?.name ?? null
  return a.treatment_type ?? null
}

function appointmentProfessional(a: Appointment): string | null {
  if (!a.professional) return null
  const u = a.professional
  const full = [u.first_name, u.last_name].filter(Boolean).join(' ').trim()
  return full || u.email || null
}

const proximityBadge = computed(() => {
  if (!props.nextAppointment) return null
  return nextAppointmentProximity(props.nextAppointment.start_time, t)
})
</script>

<template>
  <UCard
    role="region"
    aria-labelledby="visit-summary-title"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-history"
          class="w-5 h-5 text-default shrink-0"
          aria-hidden="true"
        />
        <h2
          id="visit-summary-title"
          class="text-h2 text-default"
        >
          {{ t('patients.visitSummary.title') }}
        </h2>
      </div>
    </template>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6 divide-y md:divide-y-0 md:divide-x divide-default">
      <!-- Last visit -->
      <section class="md:pr-6 pb-4 md:pb-0">
        <div class="flex items-center gap-1.5 text-caption uppercase tracking-wide text-subtle mb-2">
          <UIcon
            name="i-lucide-history"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.visitSummary.lastVisit') }}
        </div>
        <div v-if="lastVisit">
          <p class="text-body text-default font-medium">
            {{ appointmentDate(lastVisit) }}
          </p>
          <p
            v-if="appointmentTreatment(lastVisit)"
            class="text-body text-default"
          >
            {{ appointmentTreatment(lastVisit) }}
          </p>
          <p
            v-if="appointmentProfessional(lastVisit)"
            class="text-caption text-subtle"
          >
            {{ appointmentProfessional(lastVisit) }}
          </p>
        </div>
        <p
          v-else
          class="text-body text-subtle"
        >
          {{ t('patients.visitSummary.noLastVisit') }}
        </p>
      </section>

      <!-- Next appointment -->
      <section class="md:pl-6 pt-4 md:pt-0">
        <div class="flex items-center gap-1.5 text-caption uppercase tracking-wide text-subtle mb-2">
          <UIcon
            name="i-lucide-calendar-clock"
            class="w-3.5 h-3.5"
            aria-hidden="true"
          />
          {{ t('patients.visitSummary.nextAppointment') }}
          <UBadge
            v-if="proximityBadge"
            :color="proximityBadge.color"
            variant="subtle"
            size="sm"
            class="ml-1 normal-case"
          >
            {{ proximityBadge.label }}
          </UBadge>
        </div>
        <div v-if="nextAppointment">
          <p class="text-body text-default font-medium">
            {{ appointmentDate(nextAppointment) }}
            <span
              v-if="appointmentTime(nextAppointment)"
              class="text-default"
            >· {{ appointmentTime(nextAppointment) }}</span>
          </p>
          <p
            v-if="appointmentTreatment(nextAppointment)"
            class="text-body text-default"
          >
            {{ appointmentTreatment(nextAppointment) }}
          </p>
          <p
            v-if="appointmentProfessional(nextAppointment)"
            class="text-caption text-subtle"
          >
            {{ appointmentProfessional(nextAppointment) }}
          </p>
          <p
            v-if="nextAppointment.cabinet"
            class="text-caption text-subtle"
          >
            {{ nextAppointment.cabinet }}
          </p>
        </div>
        <p
          v-else
          class="text-body text-subtle"
        >
          {{ t('patients.visitSummary.noNextAppointment') }}
        </p>
      </section>
    </div>
  </UCard>
</template>
