<script setup lang="ts">
import type { ClinicHours, ClinicOverride, ClinicOverridePayload, WeekdayShifts } from '../../composables/useClinicHours'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const {
  fetchHours,
  updateHours,
  fetchOverrides,
  createOverride,
  updateOverride,
  deleteOverride
} = useClinicHours()

const canWrite = computed(() => can(PERMISSIONS.schedules.clinicHoursWrite))

const hours = ref<ClinicHours | null>(null)
const overrides = ref<ClinicOverride[]>([])
const days = ref<WeekdayShifts[]>([])
const isLoading = ref(true)
const isSaving = ref(false)

const showOverrideModal = ref(false)
const editingOverride = ref<ClinicOverride | null>(null)
const overrideForm = ref<ClinicOverridePayload>({
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  kind: 'closed',
  reason: '',
  shifts: []
})

const kindLabels = computed(() => ({
  closed: t('schedules.overrides.closed'),
  custom_hours: t('schedules.overrides.customHours')
}))

async function load() {
  isLoading.value = true
  try {
    const data = await fetchHours()
    hours.value = data
    days.value = data.days
    overrides.value = await fetchOverrides()
  } finally {
    isLoading.value = false
  }
}

async function save() {
  isSaving.value = true
  try {
    const cleanDays = days.value.map(d => ({
      weekday: d.weekday,
      shifts: d.shifts.map(s => ({ start_time: s.start_time, end_time: s.end_time }))
    }))
    const updated = await updateHours({ days: cleanDays })
    hours.value = updated
    days.value = updated.days
    toast.add({ title: t('schedules.clinicHours.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('schedules.clinicHours.savedError'), description: errorDetail(e), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

function openAddOverride() {
  editingOverride.value = null
  const today = new Date().toISOString().slice(0, 10)
  overrideForm.value = {
    start_date: today,
    end_date: today,
    kind: 'closed',
    reason: '',
    shifts: []
  }
  showOverrideModal.value = true
}

function openEditOverride(o: ClinicOverride) {
  editingOverride.value = o
  overrideForm.value = {
    start_date: o.start_date,
    end_date: o.end_date,
    kind: o.kind,
    reason: o.reason ?? '',
    shifts: o.shifts.map(s => ({ start_time: s.start_time, end_time: s.end_time }))
  }
  showOverrideModal.value = true
}

function addShiftToOverride() {
  overrideForm.value.shifts.push({ start_time: '09:00:00', end_time: '14:00:00' })
}

function removeShiftFromOverride(idx: number) {
  overrideForm.value.shifts.splice(idx, 1)
}

async function saveOverride() {
  const payload: ClinicOverridePayload = {
    start_date: overrideForm.value.start_date,
    end_date: overrideForm.value.end_date,
    kind: overrideForm.value.kind,
    reason: overrideForm.value.reason || null,
    shifts: overrideForm.value.kind === 'closed' ? [] : overrideForm.value.shifts
  }
  try {
    if (editingOverride.value) {
      await updateOverride(editingOverride.value.id, payload)
    } else {
      await createOverride(payload)
    }
    overrides.value = await fetchOverrides()
    showOverrideModal.value = false
  } catch (err: unknown) {
    const fetchError = err as { data?: { message?: string } }
    toast.add({
      title: t('common.error'),
      description: fetchError.data?.message ?? '',
      color: 'error'
    })
  }
}

async function confirmDelete(o: ClinicOverride) {
  if (!window.confirm(t('schedules.overrides.confirmDelete'))) return
  await deleteOverride(o.id)
  overrides.value = await fetchOverrides()
}

function timeForInput(value: string): string {
  return value.length >= 5 ? value.substring(0, 5) : value
}

function padTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value
}

onMounted(load)
</script>

<template>
  <div>
    <USkeleton
      v-if="isLoading"
      class="h-40 w-full"
    />

    <div
      v-else
      class="space-y-6"
    >
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('schedules.clinicHours.weeklyTemplate') }}
          </h2>
        </template>

        <WeeklyShiftGrid
          v-model="days"
          :disabled="!canWrite"
        />

        <template #footer>
          <div class="flex justify-end">
            <UButton
              v-if="canWrite"
              :loading="isSaving"
              icon="i-lucide-save"
              @click="save"
            >
              {{ t('schedules.clinicHours.save') }}
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
          @delete="confirmDelete"
        />
      </UCard>
    </div>

    <UModal v-model:open="showOverrideModal">
      <template #content>
        <div class="p-6 space-y-4">
          <h3 class="text-lg font-semibold">
            {{ editingOverride ? t('schedules.clinicHours.editOverride') : t('schedules.clinicHours.addOverride') }}
          </h3>

          <UFormField :label="t('schedules.overrides.kind')">
            <USelect
              v-model="overrideForm.kind"
              :items="[
                { label: t('schedules.overrides.closed'), value: 'closed' },
                { label: t('schedules.overrides.customHours'), value: 'custom_hours' }
              ]"
            />
          </UFormField>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <UFormField :label="t('schedules.overrides.startDate')">
              <UInput
                v-model="overrideForm.start_date"
                type="date"
              />
            </UFormField>
            <UFormField :label="t('schedules.overrides.endDate')">
              <UInput
                v-model="overrideForm.end_date"
                type="date"
              />
            </UFormField>
          </div>

          <UFormField :label="t('schedules.overrides.reason')">
            <UInput
              v-model="overrideForm.reason"
              :placeholder="t('schedules.overrides.reasonPlaceholder')"
            />
          </UFormField>

          <div
            v-if="overrideForm.kind === 'custom_hours'"
            class="space-y-2"
          >
            <label class="text-sm font-medium">{{ t('schedules.weekday.addShift') }}</label>
            <div
              v-for="(s, idx) in overrideForm.shifts"
              :key="idx"
              class="flex items-center gap-2"
            >
              <UInput
                type="time"
                :model-value="timeForInput(s.start_time)"
                size="sm"
                class="w-28"
                @update:model-value="(v) => (overrideForm.shifts[idx]!.start_time = padTime(String(v)))"
              />
              <span class="text-gray-400">—</span>
              <UInput
                type="time"
                :model-value="timeForInput(s.end_time)"
                size="sm"
                class="w-28"
                @update:model-value="(v) => (overrideForm.shifts[idx]!.end_time = padTime(String(v)))"
              />
              <UButton
                color="neutral"
                variant="ghost"
                icon="i-lucide-x"
                size="xs"
                @click="removeShiftFromOverride(idx)"
              />
            </div>
            <UButton
              size="xs"
              variant="soft"
              icon="i-lucide-plus"
              @click="addShiftToOverride"
            >
              {{ t('schedules.weekday.addShift') }}
            </UButton>
          </div>

          <div class="flex justify-end gap-2 pt-2">
            <UButton
              variant="ghost"
              @click="showOverrideModal = false"
            >
              {{ t('schedules.overrides.cancel') }}
            </UButton>
            <UButton @click="saveOverride">
              {{ t('schedules.overrides.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
