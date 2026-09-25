<script setup lang="ts">
/**
 * Staff attendance page: clock in/out per member, today's event feed,
 * and a daily pairing report. Small vertical slice — no shifts,
 * rosters, or overtime math (see module CLAUDE.md Later).
 */
import type { AttendanceEvent, AttendanceReportRow, StaffMember } from '../../composables/useAttendance'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'
import { clinicToday } from '~~/app/utils/wallClock'

definePageMeta({ middleware: ['auth'] })

const { t, locale } = useI18n()
const { can } = usePermissions()
const { clock, listEvents, dailyReport, listStaff } = useAttendance()
const { currentClinic } = useClinic()
const toast = useToast()

const canWrite = computed(() => can(PERMISSIONS.staffAttendance.write))

if (!can(PERMISSIONS.staffAttendance.read)) await navigateTo('/')

const staff = ref<StaffMember[]>([])
// Default day in the clinic's timezone — the shared core helper
// (#474 cross-ref: one copy, not one per module).
const today = ref(clinicToday(currentClinic.value?.timezone))
const events = ref<AttendanceEvent[]>([])
const report = ref<AttendanceReportRow[]>([])
const isLoading = ref(false)
const errorMessage = ref('')
const clockTarget = ref<string | undefined>(undefined)
const clockNote = ref('')

const staffOptions = computed(() =>
  staff.value.map(s => ({ label: `${s.first_name} ${s.last_name}`, value: s.id }))
)

function memberName(id: string): string {
  const s = staff.value.find(m => m.id === id)
  return s ? `${s.first_name} ${s.last_name}` : id
}

function formatHours(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const hf = new Intl.NumberFormat(locale.value, { style: 'unit', unit: 'hour', maximumFractionDigits: 0 })
  const mf = new Intl.NumberFormat(locale.value, { style: 'unit', unit: 'minute', maximumFractionDigits: 0 })
  return `${hf.format(h)} ${mf.format(m)}`
}

function formatTime(iso: string): string {
  const tz = currentClinic.value?.timezone
  try {
    return new Intl.DateTimeFormat(locale.value, {
      hour: '2-digit',
      minute: '2-digit',
      ...(tz ? { timeZone: tz } : {})
    }).format(new Date(iso))
  } catch {
    return new Date(iso).toLocaleTimeString()
  }
}

async function refresh() {
  isLoading.value = true
  try {
    staff.value = await listStaff()
    events.value = await listEvents(today.value)
    report.value = await dailyReport(today.value)
  } finally {
    isLoading.value = false
  }
}

async function punch(kind: 'in' | 'out') {
  if (!clockTarget.value) return
  errorMessage.value = ''
  try {
    await clock(clockTarget.value, kind, clockNote.value || undefined)
    clockNote.value = ''
    await refresh()
  } catch (e: unknown) {
    errorMessage.value = errorDetail(e) ?? String(e)
    toast.add({ title: t('staffAttendance.clockTitle'), description: errorMessage.value, color: 'error' })
  }
}

onMounted(refresh)
watch(today, refresh)
</script>

<template>
  <div class="space-y-4 p-4">
    <h1 class="text-h2">
      {{ t('staffAttendance.title') }}
    </h1>

    <UCard v-if="canWrite">
      <template #header>
        {{ t('staffAttendance.clockTitle') }}
      </template>
      <div class="flex flex-wrap items-end gap-2">
        <UFormField :label="t('staffAttendance.member')">
          <USelectMenu
            v-model="clockTarget"
            value-key="value"
            :items="staffOptions"
            :placeholder="t('staffAttendance.pickMember')"
          />
        </UFormField>
        <UFormField :label="t('staffAttendance.note')">
          <UInput
            v-model="clockNote"
            :placeholder="t('staffAttendance.notePlaceholder')"
          />
        </UFormField>
        <UButton
          :disabled="!clockTarget"
          @click="punch('in')"
        >
          {{ t('staffAttendance.clockIn') }}
        </UButton>
        <UButton
          color="neutral"
          variant="outline"
          :disabled="!clockTarget"
          @click="punch('out')"
        >
          {{ t('staffAttendance.clockOut') }}
        </UButton>
      </div>
    </UCard>

    <div class="grid gap-4 md:grid-cols-2">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span>{{ t('staffAttendance.today') }}</span>
            <UInput
              v-model="today"
              type="date"
            />
          </div>
        </template>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="events.length === 0"
          class="text-sm text-muted"
        >
          {{ t('staffAttendance.noEvents') }}
        </p>
        <ul
          v-else
          class="space-y-1 text-sm"
        >
          <li
            v-for="event in events"
            :key="event.id"
          >
            <UBadge :color="event.kind === 'in' ? 'success' : 'neutral'">
              {{ t(`staffAttendance.${event.kind}`) }}
            </UBadge>
            {{ memberName(event.user_id) }}
            <span class="text-muted">{{ formatTime(event.at) }}</span>
          </li>
        </ul>
      </UCard>

      <UCard>
        <template #header>
          {{ t('staffAttendance.report') }}
        </template>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="report.length === 0"
          class="text-sm text-muted"
        >
          {{ t('staffAttendance.noEvents') }}
        </p>
        <ul
          v-else
          class="space-y-1 text-sm"
        >
          <li
            v-for="row in report"
            :key="row.user_id"
            class="flex justify-between"
          >
            <span>{{ row.full_name }}</span>
            <span>{{ formatHours(row.seconds) }}{{ row.open ? ' (' + t('staffAttendance.openShift') + ')' : '' }}</span>
          </li>
        </ul>
      </UCard>
    </div>
  </div>
</template>
