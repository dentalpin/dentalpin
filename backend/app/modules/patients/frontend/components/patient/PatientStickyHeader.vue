<script setup lang="ts">
/**
 * PatientStickyHeader — persistent patient context bar.
 *
 * Renders at the top of the patient-detail page above the UTabs strip
 * and stays in view as the user scrolls into deep tabs. Two visual
 * lanes:
 *
 * - Identity lane (left): avatar · name + status · age · ID · contact
 *   actions (phone + email as icon buttons with tooltip).
 * - Signals lane (right): clinical alert chips from
 *   ``patient.header.alerts`` + Edit and Acciones buttons.
 *
 * The legacy ``patient.summary.actions`` slot (recalls "Set recall",
 * etc.) is no longer rendered in the header. It overflowed the bar
 * and competed with identity. Those module actions now live where
 * they belong — inside the Quick-Actions card on the Resumen grid.
 */

import type { PatientExtended } from '~~/app/types'

interface Props {
  patient: PatientExtended
}

const props = defineProps<Props>()

const emit = defineEmits<{
  edit: []
  back: []
  archive: []
  newAppointment: []
  newNote: []
  collect: []
}>()

const { t } = useI18n()

const fullName = computed(() => `${props.patient.first_name} ${props.patient.last_name}`)

const initials = computed(() => {
  const first = props.patient.first_name?.[0] ?? ''
  const last = props.patient.last_name?.[0] ?? ''
  return (first + last).toUpperCase() || '?'
})

const age = computed(() => {
  if (!props.patient.date_of_birth) return null
  const today = new Date()
  const birth = new Date(props.patient.date_of_birth)
  let years = today.getFullYear() - birth.getFullYear()
  const m = today.getMonth() - birth.getMonth()
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) years--
  return years
})

const genderLabel = computed(() => {
  const g = props.patient.gender
  if (!g) return null
  const map: Record<string, string> = {
    male: t('patients.gender.male'),
    female: t('patients.gender.female'),
    other: t('patients.gender.other'),
    prefer_not_say: t('patients.gender.preferNotSay')
  }
  return map[g] ?? null
})

const statusColor = computed(() => props.patient.status === 'active' ? 'success' : 'neutral')
const isArchived = computed(() => props.patient.status === 'archived')

const actionItems = computed(() => [
  {
    label: t('patientDetail.actions.newAppointment', 'Nueva cita'),
    icon: 'i-lucide-calendar-plus',
    onSelect: () => emit('newAppointment')
  },
  {
    label: t('patientDetail.actions.collect', 'Cobrar'),
    icon: 'i-lucide-wallet',
    onSelect: () => emit('collect')
  },
  {
    label: t('patientDetail.actions.newNote', 'Nueva nota'),
    icon: 'i-lucide-edit',
    onSelect: () => emit('newNote')
  },
  {
    type: 'separator' as const
  },
  {
    label: t('patients.archive'),
    icon: 'i-lucide-archive',
    color: 'error' as const,
    onSelect: () => emit('archive')
  }
])
</script>

<template>
  <header
    class="patient-sticky-header sticky top-0 z-30 -mx-4 sm:mx-0 bg-surface/90 backdrop-blur border-b border-default px-4 sm:px-3 py-2.5"
    :aria-label="t('patients.header.ariaLabel')"
  >
    <div class="flex items-center gap-3 sm:gap-4">
      <UButton
        variant="ghost"
        color="neutral"
        size="sm"
        icon="i-lucide-arrow-left"
        :aria-label="t('common.back', 'Volver')"
        class="shrink-0"
        @click="emit('back')"
      />

      <UAvatar
        v-if="patient.photo_url"
        :src="patient.photo_url"
        :alt="fullName"
        size="lg"
        class="shrink-0 ring-2 ring-[var(--color-border-subtle)]"
      />
      <UAvatar
        v-else
        :text="initials"
        size="lg"
        class="shrink-0 ring-2 ring-[var(--color-border-subtle)]"
        :ui="{ text: 'font-semibold' }"
      />

      <!-- Identity column -->
      <div class="min-w-0 flex-1 flex flex-col gap-0.5">
        <!-- Name + status -->
        <div class="flex items-center gap-2 min-w-0">
          <h1 class="text-h1 text-default font-semibold truncate">
            {{ fullName }}
          </h1>
          <UBadge
            v-if="isArchived"
            color="neutral"
            size="xs"
            variant="subtle"
            class="shrink-0"
          >
            {{ t('patients.status.archived') }}
          </UBadge>
          <span
            v-else
            class="status-dot shrink-0"
            :aria-label="t('patients.status.active')"
          />
        </div>

        <!-- Metadata strip — age · gender · DNI · contact icons -->
        <div class="flex items-center gap-x-2.5 gap-y-1 flex-wrap text-caption text-muted">
          <span
            v-if="age != null"
            class="tnum"
          >
            {{ age }} {{ t('patients.years') }}
          </span>
          <span
            v-if="genderLabel"
            class="text-subtle"
          >
            ·  {{ genderLabel }}
          </span>
          <span
            v-if="patient.national_id"
            class="tnum text-subtle inline-flex items-center gap-1"
          >
            <span aria-hidden="true">·</span>
            <UIcon
              name="i-lucide-id-card"
              class="w-3.5 h-3.5"
            />
            <span>{{ patient.national_id_type?.toUpperCase() }} {{ patient.national_id }}</span>
          </span>

          <!-- Contact icons — click to call/mail. No full string in the bar. -->
          <UTooltip
            v-if="patient.phone"
            :text="patient.phone"
          >
            <a
              :href="`tel:${patient.phone}`"
              class="inline-flex items-center justify-center w-7 h-7 rounded-token-sm text-primary-accent hover:bg-surface-muted transition-colors"
              :aria-label="`${t('patients.phone', 'Phone')}: ${patient.phone}`"
            >
              <UIcon
                name="i-lucide-phone"
                class="w-4 h-4"
              />
            </a>
          </UTooltip>
          <UTooltip
            v-if="patient.email"
            :text="patient.email"
          >
            <a
              :href="`mailto:${patient.email}`"
              class="inline-flex items-center justify-center w-7 h-7 rounded-token-sm text-primary-accent hover:bg-surface-muted transition-colors"
              :aria-label="`${t('patients.email', 'Email')}: ${patient.email}`"
            >
              <UIcon
                name="i-lucide-mail"
                class="w-4 h-4"
              />
            </a>
          </UTooltip>
        </div>
      </div>

      <!-- Clinical alert chips (patients_clinical slot) — desktop only.
           Slot is registered by a `.client.ts` plugin, so SSR sees an
           empty slot and the client populates it. Wrap in <ClientOnly>
           to keep both renderings aligned and avoid a hydration jump. -->
      <ClientOnly>
        <div class="hidden xl:flex items-center gap-1.5 max-w-sm flex-wrap justify-end">
          <ModuleSlot
            name="patient.header.alerts"
            :ctx="{ patient }"
          />
        </div>
      </ClientOnly>

      <!-- Edit + Acciones — always visible -->
      <UButton
        variant="outline"
        color="neutral"
        size="sm"
        icon="i-lucide-pencil"
        :aria-label="t('patientDetail.editPatient', 'Editar paciente')"
        class="shrink-0"
        @click="emit('edit')"
      >
        <span class="hidden sm:inline">{{ t('patientDetail.edit', 'Editar') }}</span>
      </UButton>

      <UDropdownMenu :items="actionItems">
        <UButton
          color="primary"
          size="sm"
          trailing-icon="i-lucide-chevron-down"
          icon="i-lucide-plus"
          class="shrink-0"
        >
          <span class="hidden sm:inline">{{ t('patientDetail.actions.label', 'Acciones') }}</span>
        </UButton>
      </UDropdownMenu>
    </div>

    <!-- Alerts row — visible below xl, fits chips on a separate line.
         Hidden when the slot has no providers via :empty:hidden. Same
         <ClientOnly> reasoning as the desktop slot above. -->
    <ClientOnly>
      <div class="xl:hidden mt-2 empty:hidden flex flex-wrap items-center gap-1.5">
        <ModuleSlot
          name="patient.header.alerts"
          :ctx="{ patient }"
        />
      </div>
    </ClientOnly>
  </header>
</template>

<style scoped>
.status-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  background-color: var(--color-success-accent);
  box-shadow: 0 0 0 3px color-mix(in oklab, var(--color-success-accent) 18%, transparent);
}
</style>
