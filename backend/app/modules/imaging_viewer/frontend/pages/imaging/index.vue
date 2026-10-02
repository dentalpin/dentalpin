<script setup lang="ts">
import { useImagingViewer, useRvgImport, type ImagingStudy, type RvgImport } from '../../composables/useImagingViewer'
import type { ApiResponse, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: 'auth' })

const { t, locale } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const router = useRouter()
const { fetchStudies } = useImagingViewer()
const { fetchImports, fetchImportCounts, triggerScan, approveImport, rejectImport } = useRvgImport()
const toast = useToast()
const api = useApi()

const studies = ref<ImagingStudy[]>([])
const total = ref(0)
const loading = ref(false)
const selectedId = ref<string | null>(null)
const patientId = computed(() => String(route.query.patient_id ?? ''))

interface PatientOption { label: string, value: string }
const patientOptions = ref<PatientOption[]>([])
const resolvingPatient = ref(false)
const canListPatients = computed(() => can(PERMISSIONS.patients.read))

async function searchPatients(term: string) {
  if (!canListPatients.value) return
  try {
    const res = await api.get<PaginatedResponse<{ id: string, first_name: string, last_name: string }>>(
      '/api/v1/patients',
      { query: { search: term || undefined, page: 1, page_size: 20 }, errorToast: false }
    )
    patientOptions.value = res.data.map(p => ({
      label: `${p.last_name}, ${p.first_name}`,
      value: p.id
    }))
  } catch {
    patientOptions.value = []
  }
}

async function resolvePickedName(id: string) {
  resolvingPatient.value = true
  try {
    const res = await api.get<ApiResponse<{ id: string, first_name: string, last_name: string }>>(
      `/api/v1/patients/${id}`,
      { errorToast: false }
    )
    patientOptions.value = [{
      label: `${res.data.last_name}, ${res.data.first_name}`,
      value: res.data.id
    }]
  } catch {
    // Never render the raw id as a label: an unresolvable ?patient_id=
    // shows a human-readable fallback instead.
    patientOptions.value = [{ label: t('imagingViewer.list.unknownPatient'), value: id }]
  } finally {
    resolvingPatient.value = false
  }
}

function pickPatient(id: string | undefined) {
  void router.replace({ query: { ...route.query, patient_id: id || undefined } })
}

if (patientId.value) void resolvePickedName(patientId.value)
else void searchPatients('')

const queue = ref<RvgImport[]>([])
const queueTotal = ref(0)
const queueLoading = ref(false)
const scanning = ref(false)
const actionError = ref<string | null>(null)

const canRvgRead = computed(() => can(PERMISSIONS.imagingViewer.rvg.read))
const canRvgWrite = computed(() => can(PERMISSIONS.imagingViewer.rvg.write))

async function load() {
  if (!patientId.value) return
  loading.value = true
  try {
    const res = await fetchStudies(patientId.value)
    studies.value = res.data
    total.value = res.total
    const first = res.data[0]
    if (!selectedId.value && first) selectedId.value = first.id
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(patientId, () => {
  selectedId.value = null
  load()
})

function modalityLabel(s: ImagingStudy) {
  return s.modality ?? t('imagingViewer.list.unknownModality')
}

function formatStudyDate(s: ImagingStudy) {
  if (!s.study_date) return t('imagingViewer.list.noStudyDate')
  const d = new Date(s.study_date)
  if (Number.isNaN(d.getTime())) return t('imagingViewer.list.noStudyDate')
  // Backend stores StudyDate as UTC midnight: format in UTC so the displayed
  // calendar day never shifts with the viewer's device timezone.
  return d.toLocaleDateString(locale.value, { timeZone: 'UTC' })
}

const queueStatuses = ['pending', 'approved', 'rejected', 'failed'] as const
type QueueStatus = typeof queueStatuses[number]
const activeQueueTab = ref<QueueStatus>('pending')
const queueCounts = ref<Record<string, number>>({})

async function loadQueue() {
  if (!canRvgRead.value) return
  queueLoading.value = true
  actionError.value = null
  try {
    const [res, counts] = await Promise.all([
      fetchImports(activeQueueTab.value),
      fetchImportCounts()
    ])
    queue.value = res.data
    queueTotal.value = res.total
    queueCounts.value = counts
  } catch {
    actionError.value = t('imagingViewer.rvg.loadFailed')
  } finally {
    queueLoading.value = false
  }
}

function selectQueueTab(status: QueueStatus) {
  if (activeQueueTab.value === status) return
  activeQueueTab.value = status
  void loadQueue()
}

async function scanNow() {
  scanning.value = true
  actionError.value = null
  try {
    const counts = await triggerScan()
    toast.add({
      title: t('imagingViewer.rvg.scanSummary', {
        scanned: counts.scanned ?? 0,
        created: counts.created ?? 0,
        approved: counts.approved ?? 0,
        failed: counts.failed ?? 0
      }),
      color: (counts.failed ?? 0) > 0 ? 'warning' : 'success'
    })
    await loadQueue()
  } catch {
    actionError.value = t('imagingViewer.rvg.scanFailed')
  } finally {
    scanning.value = false
  }
}

async function approve(row: RvgImport, targetPatientId: string | null) {
  if (!targetPatientId) return
  actionError.value = null
  try {
    await approveImport(row.id, targetPatientId)
    await loadQueue()
  } catch {
    actionError.value = t('imagingViewer.rvg.actionFailed')
  }
}

async function reject(row: RvgImport) {
  actionError.value = null
  try {
    await rejectImport(row.id)
    await loadQueue()
  } catch {
    actionError.value = t('imagingViewer.rvg.actionFailed')
  }
}

function suggestionLabel(row: RvgImport) {
  if (row.suggested_patient_id) {
    return t('imagingViewer.rvg.suggested', { score: row.match_score ?? 0 })
  }
  if (row.match_reason === 'ambiguous') return t('imagingViewer.rvg.ambiguous')
  return t('imagingViewer.rvg.noSuggestion')
}

onMounted(loadQueue)
</script>

<template>
  <div class="flex flex-col gap-4 p-4">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h1 class="text-xl font-semibold">
        {{ t('imagingViewer.list.title') }}
      </h1>
      <USelectMenu
        v-if="canListPatients"
        :model-value="resolvingPatient ? undefined : (patientId || undefined)"
        :items="patientOptions"
        :loading="resolvingPatient"
        value-key="value"
        :placeholder="t('imagingViewer.list.pickPatient')"
        :search-input="{ placeholder: t('imagingViewer.list.searchPatients') }"
        class="w-72"
        @update:model-value="pickPatient($event as string | undefined)"
        @update:search-term="searchPatients"
      />
    </div>

    <UAlert
      v-if="!patientId"
      color="info"
      :title="t('imagingViewer.list.noPatient')"
      :description="t('imagingViewer.list.noPatientHint')"
    />

    <template v-else>
      <USkeleton
        v-if="loading"
        class="h-24 w-full"
      />
      <UAlert
        v-else-if="studies.length === 0"
        color="info"
        :title="t('imagingViewer.list.empty')"
      />
      <div
        v-else
        class="grid grid-cols-1 gap-4 lg:grid-cols-3"
      >
        <UCard
          v-for="s in studies"
          :key="s.id"
          :class="selectedId === s.id ? 'ring-2 ring-primary' : ''"
          class="cursor-pointer"
          @click="selectedId = s.id"
        >
          <template #header>
            <span class="font-medium">{{ modalityLabel(s) }}</span>
          </template>
          <!-- The study date is what a clinician recognises; the opaque
               study_uid is a machine identifier and stays a tooltip, so
               the card reads as a study rather than a hash. -->
          <UTooltip
            v-if="s.study_uid"
            :text="s.study_uid"
          >
            <p class="text-sm text-gray-500">
              {{ formatStudyDate(s) }}
            </p>
          </UTooltip>
          <p
            v-else
            class="text-sm text-gray-500"
          >
            {{ t('imagingViewer.list.noStudyDate') }}
          </p>
        </UCard>
      </div>

      <div
        v-if="selectedId && can(PERMISSIONS.imagingViewer.studies.read)"
        class="flex flex-col gap-2"
      >
        <AnnotationPanel :study-id="selectedId" />
        <p class="text-xs text-gray-500">
          {{ t('imagingViewer.viewer.visualizationNote') }}
        </p>
      </div>
    </template>

    <UCard v-if="canRvgRead">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('imagingViewer.rvg.title') }}</span>
          <UButton
            v-if="canRvgWrite"
            icon="i-lucide-refresh-cw"
            :loading="scanning"
            @click="scanNow()"
          >
            {{ t('imagingViewer.rvg.scanNow') }}
          </UButton>
        </div>
      </template>
      <div class="flex flex-wrap gap-1">
        <UButton
          v-for="s in queueStatuses"
          :key="s"
          size="xs"
          :variant="activeQueueTab === s ? 'solid' : 'soft'"
          @click="selectQueueTab(s)"
        >
          {{ t(`imagingViewer.rvg.status.${s}`) }}
          <UBadge
            size="xs"
            :color="activeQueueTab === s ? 'neutral' : 'info'"
            variant="soft"
          >
            {{ queueCounts[s] ?? 0 }}
          </UBadge>
        </UButton>
      </div>
      <UAlert
        v-if="actionError"
        color="error"
        :title="actionError"
      />
      <USkeleton
        v-if="queueLoading"
        class="h-16 w-full"
      />
      <UAlert
        v-else-if="queue.length === 0"
        color="info"
        :title="t('imagingViewer.rvg.empty')"
      />
      <ul
        v-else
        class="flex flex-col gap-2"
      >
        <li
          v-for="row in queue"
          :key="row.id"
          class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 pb-2"
        >
          <div>
            <p class="text-sm font-medium">
              {{ row.filename }}
            </p>
            <p
              v-if="activeQueueTab === 'pending'"
              class="text-xs text-gray-500"
            >
              {{ suggestionLabel(row) }}
            </p>
            <p
              v-if="row.error"
              class="text-xs text-red-500"
            >
              {{ row.error }}
            </p>
          </div>
          <div
            v-if="canRvgWrite && activeQueueTab === 'pending'"
            class="flex gap-2"
          >
            <UButton
              v-if="row.suggested_patient_id"
              size="sm"
              @click="approve(row, row.suggested_patient_id)"
            >
              {{ t('imagingViewer.rvg.approveSuggestion') }}
            </UButton>
            <UButton
              v-if="patientId && patientId !== row.suggested_patient_id"
              size="sm"
              variant="soft"
              @click="approve(row, patientId)"
            >
              {{ t('imagingViewer.rvg.approveCurrentPatient') }}
            </UButton>
            <UButton
              size="sm"
              color="error"
              variant="soft"
              @click="reject(row)"
            >
              {{ t('imagingViewer.rvg.reject') }}
            </UButton>
          </div>
        </li>
      </ul>
    </UCard>
  </div>
</template>
