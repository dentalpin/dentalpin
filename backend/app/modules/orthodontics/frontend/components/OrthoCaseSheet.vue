<script setup lang="ts">
/**
 * Orthodontic case sheet: header, in-mouth-now wires, Month X of ~N
 * progress, status chips, photo evolution (media attachments +
 * before/after pairing), register-control sheet, controls timeline.
 * Reused by the patient sub-tab and the /orthodontics inbox.
 */
import type { OrthoCase, OrthoControl, OrthoSettings } from '../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{ caseId: string }>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const api = useApi()
const { getCase, changeStatus, listControls, registerControl, getSettings } = useOrthodontics()

const canControl = computed(() => can(PERMISSIONS.orthodontics.controlsWrite))
const canPhoto = computed(() => can(PERMISSIONS.documents.write))
const canAttach = computed(() => can(PERMISSIONS.attachments.read))

const item = ref<OrthoCase | null>(null)
const controls = ref<OrthoControl[]>([])
const settings = ref<OrthoSettings | null>(null)
const attachments = ref<{ id: string, document: { id: string } | null }[]>([])
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

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

function monthIndex(): number | null {
  if (!item.value || controls.value.length === 0) return null
  return controls.value.length
}

async function refresh() {
  isLoading.value = true
  try {
    item.value = await getCase(props.caseId)
    controls.value = await listControls(props.caseId)
    settings.value = await getSettings()
    if (canAttach.value) {
      const res = await api.get<{ data: { id: string, document: { id: string } | null }[] }>(
        '/api/v1/media/attachments',
        { query: { owner_type: 'ortho_case', owner_id: props.caseId } }
      )
      attachments.value = res.data
    }
  } finally {
    isLoading.value = false
  }
}

function toggleProcedure(key: string) {
  const i = ctlProcedures.value.indexOf(key)
  if (i >= 0) ctlProcedures.value.splice(i, 1)
  else ctlProcedures.value.push(key)
}

async function saveControl() {
  await registerControl(props.caseId, {
    upper_wire: ctlUpper.value,
    lower_wire: ctlLower.value,
    procedures: ctlProcedures.value,
    procedures_other: ctlOther.value || null,
    aligner_number: ctlAligner.value,
    hygiene: ctlHygiene.value,
    notes: ctlNotes.value || null,
    next_control_weeks: ctlWeeks.value
  })
  showControl.value = false
  ctlUpper.value = null
  ctlLower.value = null
  ctlProcedures.value = []
  ctlOther.value = ''
  ctlHygiene.value = null
  ctlAligner.value = null
  ctlNotes.value = ''
  await refresh()
}

async function saveStatus() {
  if (!item.value || !newStatus.value) return
  item.value = await changeStatus(item.value.id, newStatus.value, statusNote.value || null)
  showStatus.value = false
  newStatus.value = ''
  statusNote.value = ''
}

async function onPhotoPicked(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !item.value || !canPhoto.value) return
  const form = new FormData()
  form.append('file', file)
  form.append('media_kind', 'photo')
  const up = await api.post<{ data: { id: string } }>(
    `/api/v1/media/patients/${item.value.patient_id}/photos`,
    form
  )
  await api.post('/api/v1/media/attachments', {
    document_id: up.data.id,
    owner_type: 'ortho_case',
    owner_id: item.value.id
  })
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
          v-if="item.estimated_months && monthIndex() !== null"
          class="text-gray-500"
        >
          {{ t('orthodontics.inbox.monthOf', { x: monthIndex(), n: item.estimated_months }) }}
        </span>
        <span
          v-if="item.next_due"
          class="text-gray-500"
        >
          {{ t('orthodontics.inbox.nextDue') }}: {{ formatDate(item.next_due) }}
        </span>
        <div class="ms-auto flex gap-2">
          <UButton
            v-if="canControl"
            size="sm"
            icon="i-lucide-plus"
            @click="showControl = true"
          >
            {{ t('orthodontics.control.new') }}
          </UButton>
          <UButton
            size="sm"
            variant="soft"
            @click="showStatus = true"
          >
            {{ t('orthodontics.case.changeStatus') }}
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
            :label="p"
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
                {{ p }}
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
  </div>
  <USkeleton
    v-else-if="isLoading"
    class="h-32"
  />
</template>
