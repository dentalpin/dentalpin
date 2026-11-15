<script setup lang="ts">
import type { AssistantOverride, AssistantOverridePayload, AssistantWorkload, AssistantConflict } from '../../composables/useAssistantHours'
import type { WeekdayShifts } from '../../composables/useClinicHours'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'
import { toISODate } from '~~/app/utils/wallClock'

const { t } = useI18n()
const toast = useToast()
const auth = useAuth()
const { can } = usePermissions()
const selectedAssistant = ref<string | undefined>()
const {
  fetchAssistants, fetchHours, updateHours, fetchOverrides,
  createOverride, updateOverride, deleteOverride, fetchWorkload
} = useAssistantHours()

const canManage = computed(() => can(PERMISSIONS.schedules.assistantRead) || can(PERMISSIONS.schedules.assistantWrite))
const canWrite = computed(() => can(PERMISSIONS.schedules.assistantWrite)
  || (selectedAssistant.value === auth.user.value?.id && can(PERMISSIONS.schedules.assistantOwnWrite)))
const assistants = ref<{ user_id: string, first_name: string, last_name: string }[]>([])
const hours = ref<WeekdayShifts[]>([])
const overrides = ref<AssistantOverride[]>([])
const workload = ref<AssistantWorkload[]>([])
const conflicts = ref<AssistantConflict[]>([])
const isLoading = ref(false)
const isSaving = ref(false)
const showOverrideModal = ref(false)
const editingOverride = ref<AssistantOverride | null>(null)
const today = new Date()
const monday = new Date(today)
monday.setDate(today.getDate() - ((today.getDay() + 6) % 7))
const sunday = new Date(monday)
sunday.setDate(monday.getDate() + 6)
const periodStart = toISODate(monday)
const periodEnd = toISODate(sunday)

const assistantOptions = computed(() => assistants.value.map(user => ({
  label: `${user.first_name} ${user.last_name}`,
  value: user.user_id
})))
const kindLabels = computed(() => ({
  unavailable: t('schedules.overrides.unavailable', 'Недоступен'),
  custom_hours: t('schedules.overrides.customHours', 'Особый график')
}))
const form = ref<AssistantOverridePayload & { reason: string }>({
  start_date: toISODate(today),
  end_date: toISODate(today),
  kind: 'unavailable',
  reason: '',
  shifts: []
})

async function loadAssistant(id: string) {
  isLoading.value = true
  try {
    const [schedule, exceptions] = await Promise.all([fetchHours(id), fetchOverrides(id)])
    hours.value = schedule.days
    overrides.value = exceptions
  } catch (error) {
    toast.add({ title: t('common.error'), description: errorDetail(error), color: 'error' })
  } finally {
    isLoading.value = false
  }
}

watch(selectedAssistant, async (id) => {
  if (id) {
    await loadAssistant(id)
    if (can(PERMISSIONS.schedules.analyticsRead)) {
      try {
        const data = await fetchWorkload(periodStart, periodEnd)
        workload.value = data.rows
        conflicts.value = data.conflicts
      } catch {
        workload.value = []
        conflicts.value = []
      }
    }
  }
})

async function init() {
  if (canManage.value) {
    try {
      assistants.value = await fetchAssistants()
    } catch (error) {
      toast.add({ title: t('common.error'), description: errorDetail(error), color: 'error' })
    }
  } else if (auth.user.value) {
    assistants.value = [{
      user_id: auth.user.value.id,
      first_name: auth.user.value.first_name,
      last_name: auth.user.value.last_name
    }]
  }
  if (assistants.value.length === 1) selectedAssistant.value = assistants.value[0]?.user_id
}

async function saveHours() {
  if (!selectedAssistant.value) return
  isSaving.value = true
  try {
    const saved = await updateHours(selectedAssistant.value, hours.value.map(day => ({
      weekday: day.weekday,
      shifts: day.shifts.map(shift => ({ start_time: shift.start_time, end_time: shift.end_time }))
    })))
    hours.value = saved.days
    toast.add({ title: t('schedules.professionalHours.saved', 'График сохранён'), color: 'success' })
  } catch (error) {
    toast.add({ title: t('common.error'), description: errorDetail(error), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

function openAddOverride() {
  editingOverride.value = null
  form.value = { start_date: periodStart, end_date: periodStart, kind: 'unavailable', reason: '', shifts: [] }
  showOverrideModal.value = true
}

function openEditOverride(row: AssistantOverride) {
  editingOverride.value = row
  form.value = {
    start_date: row.start_date, end_date: row.end_date, kind: row.kind,
    reason: row.reason ?? '', shifts: row.shifts.map(s => ({ start_time: s.start_time, end_time: s.end_time }))
  }
  showOverrideModal.value = true
}

function addOverrideShift() {
  form.value.shifts.push({ start_time: '09:00:00', end_time: '14:00:00' })
}

async function saveOverride() {
  if (!selectedAssistant.value) return
  const payload: AssistantOverridePayload = {
    ...form.value,
    reason: form.value.reason || null,
    shifts: form.value.kind === 'unavailable' ? [] : form.value.shifts
  }
  try {
    if (editingOverride.value) await updateOverride(selectedAssistant.value, editingOverride.value.id, payload)
    else await createOverride(selectedAssistant.value, payload)
    overrides.value = await fetchOverrides(selectedAssistant.value)
    showOverrideModal.value = false
  } catch (error) {
    toast.add({ title: t('common.error'), description: errorDetail(error), color: 'error' })
  }
}

async function removeOverride(row: AssistantOverride) {
  if (!selectedAssistant.value || !window.confirm(t('schedules.overrides.confirmDelete'))) return
  try {
    await deleteOverride(selectedAssistant.value, row.id)
    overrides.value = await fetchOverrides(selectedAssistant.value)
  } catch (error) {
    toast.add({ title: t('common.error'), description: errorDetail(error), color: 'error' })
  }
}

function conflictLabel(conflict: AssistantConflict) {
  return conflict.kind === 'overlap'
    ? t('schedules.assistants.overlap', 'Пересекаются две записи ассистента')
    : t('schedules.assistants.outsideShift', 'Запись выходит за рабочий график ассистента')
}

onMounted(() => void init())
</script>

<template>
  <div class="space-y-6">
    <header>
      <h1 class="text-display text-default">
        {{ t('schedules.assistants.title', 'График ассистентов') }}
      </h1>
      <p class="mt-1 text-sm text-muted">
        {{ t('schedules.assistants.description', 'Настройте рабочие часы и исключения. Загрузка и пересечения рассчитаны по назначенным записям.') }}
      </p>
    </header>

    <UCard v-if="canManage">
      <UFormField :label="t('schedules.assistants.select', 'Ассистент')">
        <USelect
          v-model="selectedAssistant"
          :items="assistantOptions"
          :placeholder="t('schedules.assistants.select', 'Выберите ассистента')"
        />
      </UFormField>
    </UCard>

    <UAlert
      v-if="assistants.length === 0 && !canManage"
      color="warning"
      :title="t('schedules.assistants.noAssistant', 'Для этого аккаунта не настроен график ассистента')"
    />
    <USkeleton
      v-else-if="isLoading"
      class="h-48 w-full"
    />
    <template v-else-if="selectedAssistant">
      <UCard>
        <template #header>
          <h2 class="font-semibold">
            {{ t('schedules.assistants.weekly', 'Еженедельные часы') }}
          </h2>
        </template>
        <WeeklyShiftGrid
          v-model="hours"
          :disabled="!canWrite"
        />
        <template #footer>
          <div class="flex justify-end">
            <UButton
              v-if="canWrite"
              icon="i-lucide-save"
              :loading="isSaving"
              @click="saveHours"
            >
              {{ t('schedules.professionalHours.save', 'Сохранить график') }}
            </UButton>
          </div>
        </template>
      </UCard>

      <UCard>
        <OverrideCalendar
          :overrides="overrides"
          :can-write="canWrite"
          :kind-labels="kindLabels"
          @add="openAddOverride"
          @edit="openEditOverride"
          @delete="removeOverride"
        />
      </UCard>

      <UCard v-if="can(PERMISSIONS.schedules.analyticsRead)">
        <template #header>
          <div>
            <h2 class="font-semibold">
              {{ t('schedules.assistants.workload', 'Загрузка за текущую неделю') }}
            </h2><p class="text-xs text-muted">
              {{ periodStart }} — {{ periodEnd }}
            </p>
          </div>
        </template>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-default text-start text-muted">
                <th class="py-2 text-start">
                  {{ t('schedules.assistants.select', 'Ассистент') }}
                </th><th class="py-2 text-end">
                  {{ t('schedules.assistants.appointments', 'Записи') }}
                </th><th class="py-2 text-end">
                  {{ t('schedules.assistants.bookedHours', 'Занято, ч') }}
                </th><th class="py-2 text-end">
                  {{ t('schedules.assistants.load', 'Загрузка') }}
                </th><th class="py-2 text-end">
                  {{ t('schedules.assistants.conflictsCount', 'Конфликты') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in workload"
                :key="row.assistant_id"
                class="border-b border-default last:border-0"
              >
                <td class="py-3">
                  {{ row.assistant_name }}
                </td><td class="py-3 text-end tabular-nums">
                  {{ row.appointment_count }}
                </td><td class="py-3 text-end tabular-nums">
                  {{ (row.booked_minutes / 60).toFixed(1) }}
                </td><td class="py-3 text-end tabular-nums">
                  {{ Math.round(row.utilization_rate * 100) }}%
                </td><td class="py-3 text-end tabular-nums">
                  {{ row.conflict_count }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-if="conflicts.length"
          class="mt-4 space-y-2"
        >
          <UAlert
            v-for="conflict in conflicts"
            :key="`${conflict.kind}:${conflict.appointment_id}:${conflict.other_appointment_id}`"
            icon="i-lucide-triangle-alert"
            color="warning"
            variant="subtle"
            :title="conflictLabel(conflict)"
            :description="`${conflict.assistant_name} · ${new Date(conflict.start_at).toLocaleString()}–${new Date(conflict.end_at).toLocaleTimeString()}`"
          />
        </div>
        <p
          v-else
          class="mt-3 text-sm text-muted"
        >
          {{ t('schedules.assistants.noConflicts', 'Пересечений графика нет') }}
        </p>
      </UCard>
    </template>

    <UModal v-model:open="showOverrideModal">
      <template #content>
        <div class="space-y-4 p-6">
          <h3 class="text-lg font-semibold">
            {{ editingOverride ? t('schedules.professionalHours.editOverride') : t('schedules.professionalHours.addOverride') }}
          </h3>
          <div class="grid gap-3 sm:grid-cols-2">
            <UFormField :label="t('schedules.overrides.startDate')">
              <UInput
                v-model="form.start_date"
                type="date"
              />
            </UFormField>
            <UFormField :label="t('schedules.overrides.endDate')">
              <UInput
                v-model="form.end_date"
                type="date"
              />
            </UFormField>
          </div>
          <UFormField :label="t('schedules.overrides.kind')">
            <USelect
              v-model="form.kind"
              :items="[{ label: kindLabels.unavailable, value: 'unavailable' }, { label: kindLabels.custom_hours, value: 'custom_hours' }]"
            />
          </UFormField>
          <UFormField :label="t('schedules.overrides.reason')">
            <UInput v-model="form.reason" />
          </UFormField>
          <template v-if="form.kind === 'custom_hours'">
            <div
              v-for="(shift, index) in form.shifts"
              :key="index"
              class="grid grid-cols-[1fr_1fr_auto] items-end gap-2"
            >
              <UFormField :label="t('schedules.overrides.startTime')">
                <UInput
                  v-model="shift.start_time"
                  type="time"
                />
              </UFormField><UFormField :label="t('schedules.overrides.endTime')">
                <UInput
                  v-model="shift.end_time"
                  type="time"
                />
              </UFormField><UButton
                icon="i-lucide-x"
                variant="ghost"
                color="error"
                :aria-label="t('common.delete')"
                @click="form.shifts.splice(index, 1)"
              />
            </div><UButton
              variant="soft"
              icon="i-lucide-plus"
              @click="addOverrideShift"
            >
              {{ t('schedules.overrides.addShift') }}
            </UButton>
          </template>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              color="neutral"
              @click="showOverrideModal = false"
            >
              {{ t('actions.cancel') }}
            </UButton><UButton
              :disabled="form.end_date < form.start_date || (form.kind === 'custom_hours' && !form.shifts.length)"
              @click="saveOverride"
            >
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
