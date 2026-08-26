<script setup lang="ts">
import type { ProfessionalHours, ProfessionalOverride, ProfessionalOverridePayload, WeekdayShifts } from '../../composables/useProfessionalHours'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const auth = useAuth()
const { can } = usePermissions()
const { professionals, fetchProfessionals } = useProfessionals()
const {
  fetchHours,
  updateHours,
  fetchOverrides,
  createOverride,
  updateOverride,
  deleteOverride
} = useProfessionalHours()

const selectedProfessional = ref<string | undefined>(undefined)

const isAdmin = computed(() => can(PERMISSIONS.schedules.professionalRead) || can(PERMISSIONS.schedules.professionalWrite))
const canWrite = computed(() => {
  if (!selectedProfessional.value) return false
  if (can(PERMISSIONS.schedules.professionalWrite)) return true
  if (selectedProfessional.value === auth.user.value?.id && can(PERMISSIONS.schedules.professionalOwnWrite)) return true
  return false
})

const hours = ref<ProfessionalHours | null>(null)
const days = ref<WeekdayShifts[]>([])
const overrides = ref<ProfessionalOverride[]>([])
const isLoading = ref(false)
const isSaving = ref(false)

const professionalOptions = computed(() =>
  professionals.value.map(p => ({ label: `${p.first_name} ${p.last_name}`, value: p.id }))
)

const showOverrideModal = ref(false)
const editingOverride = ref<ProfessionalOverride | null>(null)
// The form keeps `reason` as a string for the input; it is normalised to
// `null` when building the payload.
type OverrideForm = Omit<ProfessionalOverridePayload, 'reason'> & { reason: string }
const overrideForm = ref<OverrideForm>({
  start_date: new Date().toISOString().slice(0, 10),
  end_date: new Date().toISOString().slice(0, 10),
  kind: 'unavailable',
  reason: '',
  shifts: []
})

const kindLabels = computed(() => ({
  unavailable: t('schedules.overrides.unavailable'),
  custom_hours: t('schedules.overrides.customHours')
}))

async function loadProfessional(id: string) {
  isLoading.value = true
  try {
    const data = await fetchHours(id)
    hours.value = data
    days.value = data.days
    overrides.value = await fetchOverrides(id)
  } finally {
    isLoading.value = false
  }
}

watch(selectedProfessional, async (id) => {
  if (id) await loadProfessional(id)
})

async function save() {
  if (!selectedProfessional.value) return
  isSaving.value = true
  try {
    const cleanDays = days.value.map(d => ({
      weekday: d.weekday,
      shifts: d.shifts.map(s => ({ start_time: s.start_time, end_time: s.end_time }))
    }))
    const updated = await updateHours(selectedProfessional.value, cleanDays)
    hours.value = updated
    days.value = updated.days
    toast.add({ title: t('schedules.professionalHours.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorDetail(e), color: 'error' })
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
    kind: 'unavailable',
    reason: '',
    shifts: []
  }
  showOverrideModal.value = true
}

function openEditOverride(o: ProfessionalOverride) {
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
  if (!selectedProfessional.value) return
  const payload: ProfessionalOverridePayload = {
    start_date: overrideForm.value.start_date,
    end_date: overrideForm.value.end_date,
    kind: overrideForm.value.kind,
    reason: overrideForm.value.reason || null,
    shifts: overrideForm.value.kind === 'unavailable' ? [] : overrideForm.value.shifts
  }
  try {
    if (editingOverride.value) {
      await updateOverride(selectedProfessional.value, editingOverride.value.id, payload)
    } else {
      await createOverride(selectedProfessional.value, payload)
    }
    overrides.value = await fetchOverrides(selectedProfessional.value)
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

async function confirmDelete(o: ProfessionalOverride) {
  if (!selectedProfessional.value) return
  if (!window.confirm(t('schedules.overrides.confirmDelete'))) return
  await deleteOverride(selectedProfessional.value, o.id)
  overrides.value = await fetchOverrides(selectedProfessional.value)
}

function timeForInput(value: string): string {
  return value.length >= 5 ? value.substring(0, 5) : value
}

function padTime(value: string): string {
  return value.length === 5 ? `${value}:00` : value
}

onMounted(async () => {
  await fetchProfessionals()
  if (!isAdmin.value && auth.user.value) {
    selectedProfessional.value = auth.user.value.id
  }
})
</script>

<template>
  <div>
    <UCard
      v-if="isAdmin"
      class="mb-4"
    >
      <UFormField :label="t('schedules.professionalHours.selectProfessional')">
        <USelect
          v-model="selectedProfessional"
          :items="professionalOptions"
          :placeholder="t('schedules.professionalHours.selectProfessional')"
        />
      </UFormField>
    </UCard>

    <USkeleton
      v-if="isLoading"
      class="h-40 w-full"
    />

    <div
      v-else-if="selectedProfessional"
      class="space-y-6"
    >
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('schedules.professionalHours.weeklyTemplate') }}
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
              {{ t('schedules.professionalHours.save') }}
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
            {{ editingOverride ? t('schedules.professionalHours.editOverride') : t('schedules.professionalHours.addOverride') }}
          </h3>

          <UFormField :label="t('schedules.overrides.kind')">
            <USelect
              v-model="overrideForm.kind"
              :items="[
                { label: t('schedules.overrides.unavailable'), value: 'unavailable' },
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
                :aria-label="t('common.remove')"
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
