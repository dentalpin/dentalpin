<script setup lang="ts">
/**
 * AppointmentsMode - View and manage patient appointments
 */

import type { Appointment, PaginatedResponse } from '~~/app/types'
import { parseWallClock } from '~~/app/utils/wallClock'

const props = defineProps<{
  patientId: string
}>()

const { t, locale } = useI18n()
// Status labels come from the canonical composable, never from a local
// copy of the vocabulary: the flat `appointments.<status>` keys this
// component used to read were a stale duplicate that never grew
// `checked_in` / `in_treatment`.
const { statusLabel } = useAppointmentStatus()
const api = useApi()
const router = useRouter()

const appointments = ref<Appointment[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const totalPages = computed(() => Math.ceil(total.value / pageSize))
const isLoading = ref(false)

async function loadAppointments() {
  isLoading.value = true
  try {
    const params = new URLSearchParams({
      patient_id: props.patientId,
      page: String(currentPage.value),
      page_size: String(pageSize)
    })
    const response = await api.get<PaginatedResponse<Appointment>>(
      `/api/v1/agenda/appointments?${params.toString()}`
    )
    appointments.value = response.data
    total.value = response.total
  } catch {
    appointments.value = []
    total.value = 0
  } finally {
    isLoading.value = false
  }
}

watch(currentPage, loadAppointments)
watch(() => props.patientId, () => {
  currentPage.value = 1
  loadAppointments()
})

onMounted(loadAppointments)

// Format date time
function formatDateTime(dateStr: string): string {
  return parseWallClock(dateStr).toLocaleString(locale.value, {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

// Status badge color
type BadgeColor = 'success' | 'warning' | 'neutral' | 'error' | 'info' | 'primary' | 'secondary'

function getStatusColor(appointmentStatus: string): BadgeColor {
  switch (appointmentStatus) {
    case 'scheduled':
      return 'info'
    case 'confirmed':
      return 'success'
    case 'checked_in':
    case 'in_treatment':
      return 'warning'
    case 'completed':
      return 'neutral'
    case 'cancelled':
      return 'error'
    case 'no_show':
      return 'error'
    default:
      return 'neutral'
  }
}

function goToAppointment(appointment: Appointment) {
  const date = appointment.start_time.split('T')[0]
  router.push(`/appointments?highlight=${appointment.id}&date=${date}`)
}
</script>

<template>
  <div class="appointments-mode">
    <!-- Header -->
    <div class="flex items-center justify-between mb-4">
      <h3 class="text-h2 text-default font-semibold flex min-w-0 items-center gap-2">
        <UIcon
          name="i-lucide-calendar"
          class="w-5 h-5"
        />
        {{ t('patientDetail.tabs.appointments') }}
        <UBadge
          v-if="total > 0"
          color="neutral"
          size="xs"
          variant="subtle"
        >
          {{ total }}
        </UBadge>
      </h3>
      <UButton
        size="sm"
        icon="i-lucide-plus"
        color="primary"
        :to="`/appointments?patient_id=${patientId}`"
      >
        {{ t('patientDetail.scheduleAppointment') }}
      </UButton>
    </div>

    <!-- Loading -->
    <div
      v-if="isLoading"
      class="space-y-3"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-12 w-full"
      />
    </div>

    <!-- Empty state -->
    <UCard
      v-else-if="total === 0"
      class="text-center py-8"
    >
      <UIcon
        name="i-lucide-calendar"
        class="w-12 h-12 text-subtle mx-auto mb-3"
      />
      <p class="text-muted mb-4">
        {{ t('patientDetail.noAppointments') }}
      </p>
      <UButton
        :to="`/appointments?patient_id=${patientId}`"
        icon="i-lucide-plus"
      >
        {{ t('patientDetail.scheduleAppointment') }}
      </UButton>
    </UCard>

    <!-- Appointments list -->
    <UCard
      v-else
      class="appointments-list-card"
    >
      <ul class="divide-y divide-[var(--color-border-subtle)]">
        <li
          v-for="appointment in appointments"
          :key="appointment.id"
          class="first:-mt-2 last:-mb-2"
        >
          <button
            type="button"
            class="appointment-row flex min-h-16 w-full items-center justify-between gap-3 rounded-token-md px-2 py-3 text-start"
            :aria-label="formatDateTime(appointment.start_time) + ' — ' + (appointment.treatment_type || '')"
            @click="goToAppointment(appointment)"
          >
            <span class="flex min-w-0 items-center gap-3">
              <span class="appointment-row-icon flex size-10 shrink-0 items-center justify-center rounded-token-md">
                <UIcon
                  name="i-lucide-calendar-clock"
                  class="size-5"
                />
              </span>
              <span class="min-w-0">
                <span class="block text-ui font-semibold text-default">
                  {{ formatDateTime(appointment.start_time) }}
                </span>
                <span class="mt-0.5 block truncate text-caption text-muted">
                  {{ appointment.treatment_type || '-' }}
                </span>
              </span>
            </span>
            <span class="flex shrink-0 items-center gap-2">
              <UBadge
                :color="getStatusColor(appointment.status)"
                variant="subtle"
              >
                {{ statusLabel(appointment.status) }}
              </UBadge>
              <UIcon
                name="i-lucide-chevron-right"
                class="size-4 text-subtle"
                aria-hidden="true"
              />
            </span>
          </button>
        </li>
      </ul>

      <PaginationBar
        v-model:page="currentPage"
        :total-pages="totalPages"
        :total="total"
        :page-size="pageSize"
      />
    </UCard>
  </div>
</template>

<style scoped>
.appointment-row {
  touch-action: manipulation;
  transition: background-color 150ms ease;
}

.appointment-row:hover {
  background-color: var(--color-surface-muted);
}

.appointment-row:focus-visible {
  outline: 3px solid color-mix(in oklab, var(--color-primary-accent) 40%, transparent);
  outline-offset: 2px;
}

.appointment-row-icon {
  background-color: var(--color-surface-muted);
  color: var(--color-primary-accent);
}

@media (prefers-reduced-motion: reduce) {
  .appointment-row {
    transition: none;
  }
}
</style>
