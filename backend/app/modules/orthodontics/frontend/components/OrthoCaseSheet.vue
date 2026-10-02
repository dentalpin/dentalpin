<script setup lang="ts">
/**
 * Orthodontic case sheet: header, in-mouth-now wires, Month X of ~N
 * progress, status chips, plan link + installments widget, photo
 * evolution (media attachments + before/after pairing),
 * register-control sheet, controls timeline.
 * Reused by the patient sub-tab and the /orthodontics inbox.
 */
import type { OrthoCase, OrthoControl, OrthoInstallments, OrthoSettings } from '../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'
import { useActiveModulesState, useModules } from '~~/app/composables/useModules'
import { orthoMonth } from '../utils/orthoMonth'

const props = defineProps<{ caseId: string }>()

const { t, te, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const api = useApi()
const { ensureLoaded: ensureModulesLoaded } = useModules()
const activeModules = useActiveModulesState()
const canCollect = computed(
  () => can(PERMISSIONS.payments.recordRead)
    && (activeModules.value ?? []).some(m => m.name === 'payments')
)
const { getCase, changeStatus, listControls, registerControl, getSettings, linkPlan, unlinkPlan, generateSchedule, getInstallments } = useOrthodontics()

const canControl = computed(() => can(PERMISSIONS.orthodontics.controlsWrite))
const canWriteCase = computed(() => can(PERMISSIONS.orthodontics.casesWrite))
// Upload creates a media document, then links it: both grants are needed.
const canPhoto = computed(() => can(PERMISSIONS.documents.write) && can(PERMISSIONS.attachments.write))
const canAttach = computed(() => can(PERMISSIONS.attachments.read))
const canPlans = computed(() => can(PERMISSIONS.treatmentPlans.read))
const canAgenda = computed(() => can(PERMISSIONS.appointments.read))

const item = ref<OrthoCase | null>(null)
const controls = ref<OrthoControl[]>([])
const settings = ref<OrthoSettings | null>(null)
const attachments = ref<{ id: string, document: { id: string } | null }[]>([])
const installments = ref<OrthoInstallments | null>(null)
const isLoading = ref(false)

const showControl = ref(false)
const ctlUpper = ref<string | null>(null)
const ctlLower = ref<string | null>(null)
const ctlProcedures = ref<string[]>([])
const ctlOther = ref('')
const ctlHygiene = ref<'good' | 'fair' | 'poor' | null>(null)
const ctlAligner = ref<number | null>(null)
const ctlNotes = ref('')
const ctlWeeks = ref<number | null>(4)
const ctlAppointment = ref<string | null>(null)
const ctlSession = ref<string | null>(null)
const upcomingAppointments = ref<{ id: string, start_time: string }[]>([])

const showStatus = ref(false)
const newStatus = ref('')
const statusNote = ref('')

/** Mirror of backend VALID_TRANSITIONS: only offer legal moves (plus the
 *  current status, accepted as a note update). Illegal clicks used to 400. */
const VALID_TRANSITIONS: Record<string, string[]> = {
  active: ['paused', 'finished', 'transferred_out'],
  paused: ['active', 'finished', 'transferred_out'],
  finished: ['active'],
  transferred_out: []
}
const allowedStatuses = computed(() => {
  const current = item.value?.status
  if (!current) return []
  return [current, ...(VALID_TRANSITIONS[current] ?? []).filter(s => s !== current)]
})

const showPlan = ref(false)
const patientPlans = ref<{ id: string, plan_number: string, status: string, items: { id: string }[] }[]>([])
const pickedPlan = ref('')
const pickedItem = ref('')

const showSchedule = ref(false)
const schedDown = ref(0)
const schedMonths = ref(12)
const schedAmount = ref(0)

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(iso))
}

function sessionStatusLabel(status: string): string {
  const key = `orthodontics.status.session_${status}`
  return te(key) ? t(key) : status
}

const isTerminal = computed(() =>
  item.value?.status === 'finished' || item.value?.status === 'transferred_out'
)

const monthIndex = computed(() => {
  if (!item.value) return null
  const until = isTerminal.value && item.value.finished_at ? new Date(item.value.finished_at) : new Date()
  return orthoMonth(item.value.start_date, until)
})

// Seeded chip keys are translated; custom clinic chips show as typed.
function procedureLabel(key: string): string {
  return te(`orthodontics.procedures.${key}`) ? t(`orthodontics.procedures.${key}`) : key
}

function notifyError(key: 'saveFailed' | 'loadFailed') {
  toast.add({ title: t(`orthodontics.errors.${key}`), color: 'error' })
}

async function refresh() {
  isLoading.value = true
  try {
    await ensureModulesLoaded()
    item.value = await getCase(props.caseId)
    controls.value = await listControls(props.caseId)
    settings.value = await getSettings()
    installments.value = null
    if (item.value.treatment_plan_id) {
      try {
        installments.value = await getInstallments(props.caseId)
      } catch {
        installments.value = null
      }
    }
    if (canAttach.value) {
      const res = await api.get<{ data: { id: string, document: { id: string } | null }[] }>(
        '/api/v1/media/attachments',
        { query: { owner_type: 'ortho_case', owner_id: props.caseId } }
      )
      attachments.value = res.data
    }
  } catch {
    notifyError('loadFailed')
  } finally {
    isLoading.value = false
  }
}

function toggleProcedure(key: string) {
  const i = ctlProcedures.value.indexOf(key)
  if (i >= 0) ctlProcedures.value.splice(i, 1)
  else ctlProcedures.value.push(key)
}

async function openControl() {
  ctlAppointment.value = null
  ctlSession.value = null
  upcomingAppointments.value = []
  if (canAgenda.value && item.value) {
    try {
      const res = await api.get<{ data: { id: string, start_time: string }[] }>(
        '/api/v1/agenda/appointments',
        { query: { patient_id: item.value.patient_id } }
      )
      const now = Date.now()
      upcomingAppointments.value = res.data.filter(a => new Date(a.start_time).getTime() >= now)
    } catch {
      upcomingAppointments.value = []
    }
  }
  showControl.value = true
}

async function saveControl() {
  try {
    await registerControl(props.caseId, {
      upper_wire: ctlUpper.value,
      lower_wire: ctlLower.value,
      procedures: ctlProcedures.value,
      procedures_other: ctlOther.value || null,
      aligner_number: ctlAligner.value,
      hygiene: ctlHygiene.value,
      notes: ctlNotes.value || null,
      next_control_weeks: ctlWeeks.value,
      appointment_id: ctlAppointment.value,
      session_id: ctlSession.value
    })
  } catch {
    notifyError('saveFailed')
    return
  }
  showControl.value = false
  ctlUpper.value = null
  ctlLower.value = null
  ctlProcedures.value = []
  ctlOther.value = ''
  ctlHygiene.value = null
  ctlAligner.value = null
  ctlNotes.value = ''
  ctlAppointment.value = null
  ctlSession.value = null
  await refresh()
}

async function saveStatus() {
  if (!item.value || !newStatus.value) return
  try {
    item.value = await changeStatus(item.value.id, newStatus.value, statusNote.value || null)
  } catch {
    notifyError('saveFailed')
    return
  }
  showStatus.value = false
  newStatus.value = ''
  statusNote.value = ''
  await refresh()
}

async function openPlanPicker() {
  pickedPlan.value = ''
  pickedItem.value = ''
  patientPlans.value = []
  if (canPlans.value && item.value) {
    try {
      const res = await api.get<{ data: { id: string, plan_number: string, status: string, items: { id: string }[] }[] }>(
        `/api/v1/treatment-plans/treatment-plans/patient/${item.value.patient_id}`
      )
      patientPlans.value = res.data
    } catch {
      patientPlans.value = []
    }
  }
  showPlan.value = true
}

const pickedPlanItems = computed(() => {
  const plan = patientPlans.value.find(p => p.id === pickedPlan.value)
  return plan ? plan.items : []
})

const pickedItemLabels = ref<Record<string, string>>({})

function pickedItemLabel(id: string, idx: number) {
  return pickedItemLabels.value[id] ?? `Item ${idx + 1}`
}

watch(pickedPlan, async (id) => {
  pickedItemLabels.value = {}
  if (!id || !canPlans.value) return
  try {
    const res = await api.get<{ data: {
      items: { id: string, treatment?: { clinical_type?: string | null, catalog_item?: { name?: string | null } | null } | null }[]
    } }>(`/api/v1/treatment-plans/treatment-plans/${id}`)
    for (const it of res.data.items ?? []) {
      pickedItemLabels.value[it.id] = it.treatment?.catalog_item?.name
        ?? it.treatment?.clinical_type
        ?? ''
    }
  } catch {
    pickedItemLabels.value = {}
  }
})

async function savePlanLink() {
  if (!pickedPlan.value || !pickedItem.value) return
  try {
    item.value = await linkPlan(props.caseId, pickedPlan.value, pickedItem.value)
    showPlan.value = false
    await refresh()
  } catch {
    notifyError('saveFailed')
  }
}

async function removePlanLink() {
  if (!confirm(t('orthodontics.plan.confirmUnlink'))) return
  try {
    item.value = await unlinkPlan(props.caseId)
    await refresh()
  } catch {
    notifyError('saveFailed')
  }
}

async function saveSchedule() {
  try {
    installments.value = await generateSchedule(props.caseId, {
      down_payment: schedDown.value,
      months: schedMonths.value,
      monthly_amount: schedAmount.value,
      down_payment_label: t('orthodontics.plan.downPayment'),
      installment_labels: Array.from(
        { length: schedMonths.value },
        (_, i) => t('orthodontics.plan.installmentN', { n: i + 1 })
      )
    })
    showSchedule.value = false
    await refresh()
  } catch {
    notifyError('saveFailed')
  }
}

async function onPhotoPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !item.value || !canPhoto.value) return
  const form = new FormData()
  form.append('file', file)
  form.append('media_kind', 'photo')
  try {
    const up = await api.post<{ data: { id: string } }>(
      `/api/v1/media/patients/${item.value.patient_id}/photos`,
      form
    )
    await api.post('/api/v1/media/attachments', {
      document_id: up.data.id,
      owner_type: 'ortho_case',
      owner_id: item.value.id
    })
  } catch {
    notifyError('saveFailed')
  } finally {
    input.value = ''
  }
  await refresh()
}

watch(() => props.caseId, refresh, { immediate: true })
</script>

<template>
  <div v-if="item">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between gap-2">
          <div>
            <div class="font-semibold">
              {{ t('orthodontics.case.inMouthNow') }}
            </div>
            <div class="text-sm text-gray-500">
              ↑ {{ item.current_upper_wire || t('orthodontics.case.noWire') }} ·
              ↓ {{ item.current_lower_wire || t('orthodontics.case.noWire') }}
            </div>
          </div>
          <UBadge
            :label="t(`orthodontics.status.${item.status}`)"
            variant="soft"
          />
        </div>
      </template>
      <div class="flex flex-wrap items-center gap-2 text-sm">
        <span>{{ t(`orthodontics.appliance.${item.appliance_type}`) }}</span>
        <span
          v-if="item.estimated_months && monthIndex !== null"
          class="text-gray-500"
        >
          {{ t('orthodontics.inbox.monthOf', { x: monthIndex, n: item.estimated_months }) }}
        </span>
        <span
          v-if="item.next_due"
          class="text-gray-500"
        >
          {{ t('orthodontics.inbox.nextDue') }}: {{ formatDate(item.next_due) }}
        </span>
        <div class="ms-auto flex gap-2">
          <UButton
            v-if="canControl && !isTerminal"
            size="sm"
            icon="i-lucide-plus"
            @click="openControl()"
          >
            {{ t('orthodontics.control.new') }}
          </UButton>
          <UButton
            v-if="canWriteCase"
            size="sm"
            variant="soft"
            @click="showStatus = true"
          >
            {{ t('orthodontics.case.changeStatus') }}
          </UButton>
        </div>
      </div>
    </UCard>

    <UAlert
      v-if="item.plan_close_suggested"
      class="mt-3"
      color="warning"
      :title="t('orthodontics.plan.closeSuggested')"
    />

    <UCard
      v-if="canPlans"
      class="mt-3"
    >
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('orthodontics.plan.title') }}</span>
          <div class="flex gap-2">
            <UButton
              v-if="canWriteCase && !item.treatment_plan_id"
              size="sm"
              variant="soft"
              @click="openPlanPicker()"
            >
              {{ t('orthodontics.plan.link') }}
            </UButton>
            <UButton
              v-if="canWriteCase && item.treatment_plan_id"
              size="sm"
              variant="soft"
              @click="removePlanLink()"
            >
              {{ t('orthodontics.plan.unlink') }}
            </UButton>
          </div>
        </div>
      </template>
      <div
        v-if="!item.treatment_plan_id"
        class="text-sm text-gray-500"
      >
        {{ t('orthodontics.plan.noLink') }}
      </div>
      <div v-else-if="installments">
        <div class="mb-2 text-sm">
          {{ t('orthodontics.plan.completed', { n: installments.completed_count }) }} ·
          {{ t('orthodontics.plan.pending', { n: installments.pending_count }) }}
        </div>
        <div class="mb-2 flex flex-wrap gap-1">
          <UBadge
            v-for="s in installments.sessions"
            :key="s.id"
            :label="`${s.sequence} · ${sessionStatusLabel(s.status)}`"
            :variant="s.status === 'completed' ? 'solid' : 'soft'"
            size="sm"
          />
        </div>
        <div class="flex gap-2">
          <UButton
            v-if="canWriteCase"
            size="sm"
            variant="soft"
            @click="showSchedule = true"
          >
            {{ t('orthodontics.plan.generate') }}
          </UButton>
          <UButton
            v-if="canCollect"
            size="sm"
            :to="`/payments?patient_id=${item.patient_id}`"
          >
            {{ t('orthodontics.plan.collect') }}
          </UButton>
        </div>
      </div>
    </UCard>

    <UCard
      v-if="canAttach"
      class="mt-3"
    >
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-semibold">{{ t('orthodontics.photos.title', { n: attachments.length }) }}</span>
          <label v-if="canPhoto">
            <UButton
              size="sm"
              variant="soft"
              icon="i-lucide-camera"
              as="span"
            >
              {{ t('orthodontics.photos.upload') }}
            </UButton>
            <input
              type="file"
              accept="image/*"
              class="hidden"
              @change="onPhotoPicked"
            >
          </label>
        </div>
      </template>
      <div
        v-if="attachments.length === 0"
        class="text-sm text-gray-500"
      >
        —
      </div>
      <div class="flex flex-wrap gap-2">
        <img
          v-for="a in attachments"
          :key="a.id"
          :src="`/api/v1/media/documents/${a.document?.id}/download?variant=thumb`"
          class="h-20 w-20 rounded object-cover"
          loading="lazy"
          alt=""
        >
      </div>
    </UCard>

    <div class="mt-3">
      <div class="mb-2 font-semibold">
        {{ t('orthodontics.control.history') }} ({{ controls.length }})
      </div>
      <div
        v-if="controls.length === 0"
        class="text-sm text-gray-500"
      >
        {{ t('orthodontics.control.empty') }}
      </div>
      <UCard
        v-for="c in controls"
        :key="c.id"
        class="mb-2"
      >
        <div class="flex flex-wrap items-center gap-2 text-sm">
          <span class="font-medium">{{ formatDate(c.performed_at) }}</span>
          <span v-if="c.upper_wire">↑ {{ c.upper_wire }}</span>
          <span v-if="c.lower_wire">↓ {{ c.lower_wire }}</span>
          <UBadge
            v-for="p in c.procedures"
            :key="p"
            :label="procedureLabel(p)"
            variant="soft"
            size="sm"
          />
          <span
            v-if="c.hygiene"
            class="inline-block h-3 w-3 rounded-full"
            :class="{
              'bg-green-500': c.hygiene === 'good',
              'bg-yellow-500': c.hygiene === 'fair',
              'bg-red-500': c.hygiene === 'poor'
            }"
          />
        </div>
        <p
          v-if="c.notes"
          class="mt-1 text-sm text-gray-600"
        >
          {{ c.notes }}
        </p>
      </UCard>
    </div>

    <UModal
      v-model:open="showControl"
      :title="t('orthodontics.control.new')"
    >
      <template #body>
        <div class="space-y-4">
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.control.wires') }}
            </div>
            <div class="flex flex-wrap gap-1">
              <UButton
                v-for="w in settings?.wires || []"
                :key="'u' + w"
                size="xs"
                :variant="ctlUpper === w ? 'solid' : 'soft'"
                @click="ctlUpper = ctlUpper === w ? null : w"
              >
                ↑ {{ w }}
              </UButton>
            </div>
            <div class="mt-1 flex flex-wrap gap-1">
              <UButton
                v-for="w in settings?.wires || []"
                :key="'l' + w"
                size="xs"
                :variant="ctlLower === w ? 'solid' : 'soft'"
                @click="ctlLower = ctlLower === w ? null : w"
              >
                ↓ {{ w }}
              </UButton>
            </div>
          </div>
          <div>
            <div class="mb-1 text-sm font-medium">
              {{ t('orthodontics.control.procedures') }}
            </div>
            <div class="flex flex-wrap gap-1">
              <UButton
                v-for="p in settings?.procedures || []"
                :key="p"
                size="xs"
                :variant="ctlProcedures.includes(p) ? 'solid' : 'soft'"
                @click="toggleProcedure(p)"
              >
                {{ procedureLabel(p) }}
              </UButton>
            </div>
            <UInput
              v-model="ctlOther"
              class="mt-2"
              :placeholder="t('orthodontics.control.proceduresOther')"
            />
          </div>
          <div class="flex gap-1">
            <UButton
              v-for="h in (['good', 'fair', 'poor'] as const)"
              :key="h"
              size="xs"
              :variant="ctlHygiene === h ? 'solid' : 'soft'"
              @click="ctlHygiene = h"
            >
              {{ t(`orthodontics.control.hygiene_${h}`) }}
            </UButton>
            <UInput
              v-if="item.appliance_type === 'aligners'"
              v-model.number="ctlAligner"
              type="number"
              min="1"
              class="ms-2 w-32"
              :placeholder="t('orthodontics.control.alignerNumber')"
            />
          </div>
          <UTextarea
            v-model="ctlNotes"
            :placeholder="t('orthodontics.control.notes')"
          />
          <div class="flex items-center gap-1">
            <span class="text-sm">{{ t('orthodontics.control.nextControl') }}:</span>
            <UButton
              v-for="w in [3, 4, 6, 8]"
              :key="w"
              size="xs"
              :variant="ctlWeeks === w ? 'solid' : 'soft'"
              @click="ctlWeeks = w"
            >
              {{ t('orthodontics.control.weeks', { n: w }) }}
            </UButton>
            <UButton
              size="xs"
              :variant="ctlWeeks === null ? 'solid' : 'soft'"
              @click="ctlWeeks = null"
            >
              {{ t('orthodontics.control.noNext') }}
            </UButton>
          </div>
          <div
            v-if="upcomingAppointments.length > 0"
            class="flex items-center gap-2"
          >
            <span class="text-sm">{{ t('orthodontics.control.appointment') }}:</span>
            <USelect
              v-model="ctlAppointment"
              :items="[{ label: '—', value: null }, ...upcomingAppointments.map(a => ({ label: formatDateTime(a.start_time), value: a.id }))]"
              value-key="value"
              label-key="label"
            />
          </div>
          <div
            v-if="installments && installments.sessions.some(s => s.status === 'pending')"
            class="flex items-center gap-2"
          >
            <span class="text-sm">{{ t('orthodontics.control.session') }}:</span>
            <USelect
              v-model="ctlSession"
              :items="[{ label: '—', value: null }, ...installments.sessions.filter(s => s.status === 'pending').map(s => ({ label: `${s.sequence} · ${s.label}`, value: s.id }))]"
              value-key="value"
              label-key="label"
            />
            <p class="text-xs text-gray-500">
              {{ t('orthodontics.control.sessionHint') }}
            </p>
          </div>
        </div>
      </template>
      <template #footer>
        <UButton @click="saveControl">
          {{ t('orthodontics.control.save') }}
        </UButton>
      </template>
    </UModal>

    <UModal
      v-model:open="showStatus"
      :title="t('orthodontics.case.changeStatus')"
    >
      <template #body>
        <div class="flex flex-wrap gap-1">
          <UButton
            v-for="s in allowedStatuses"
            :key="s"
            size="sm"
            :variant="newStatus === s ? 'solid' : 'soft'"
            @click="newStatus = s"
          >
            {{ t(`orthodontics.status.${s}`) }}
          </UButton>
        </div>
        <UInput
          v-model="statusNote"
          class="mt-3"
          :placeholder="t('orthodontics.case.statusNote')"
        />
      </template>
      <template #footer>
        <UButton
          :disabled="!newStatus"
          @click="saveStatus"
        >
          {{ t('orthodontics.case.save') }}
        </UButton>
      </template>
    </UModal>

    <UModal
      v-model:open="showPlan"
      :title="t('orthodontics.plan.link')"
    >
      <template #body>
        <div class="space-y-3">
          <USelect
            v-model="pickedPlan"
            :items="patientPlans.map(p => ({ label: `${p.plan_number} · ${p.status}`, value: p.id }))"
            value-key="value"
            label-key="label"
            :placeholder="t('orthodontics.plan.title')"
          />
          <USelect
            v-if="pickedPlanItems.length > 0"
            v-model="pickedItem"
            :items="pickedPlanItems.map((it, idx) => ({ label: pickedItemLabel(it.id, idx), value: it.id }))"
            value-key="value"
            label-key="label"
          />
        </div>
      </template>
      <template #footer>
        <UButton
          :disabled="!pickedPlan || !pickedItem"
          @click="savePlanLink"
        >
          {{ t('orthodontics.case.save') }}
        </UButton>
      </template>
    </UModal>

    <UModal
      v-model:open="showSchedule"
      :title="t('orthodontics.plan.generate')"
    >
      <template #body>
        <div class="space-y-3">
          <UInput
            v-model.number="schedDown"
            type="number"
            min="0"
            :placeholder="t('orthodontics.plan.downPayment')"
          />
          <UInput
            v-model.number="schedMonths"
            type="number"
            min="1"
            :placeholder="t('orthodontics.plan.months')"
          />
          <UInput
            v-model.number="schedAmount"
            type="number"
            min="0"
            :placeholder="t('orthodontics.plan.monthlyAmount')"
          />
        </div>
      </template>
      <template #footer>
        <UButton @click="saveSchedule">
          {{ t('orthodontics.case.save') }}
        </UButton>
      </template>
    </UModal>
  </div>
  <USkeleton
    v-else-if="isLoading"
    class="h-32"
  />
</template>
