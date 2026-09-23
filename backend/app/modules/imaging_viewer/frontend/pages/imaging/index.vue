<script setup lang="ts">
import { useImagingViewer, useRvgImport, type ImagingStudy, type RvgImport } from '../../composables/useImagingViewer'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: 'auth' })

const { t } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const { fetchStudies } = useImagingViewer()
const { fetchImports, triggerScan, approveImport, rejectImport } = useRvgImport()

const studies = ref<ImagingStudy[]>([])
const total = ref(0)
const loading = ref(false)
const selectedId = ref<string | null>(null)
const patientId = computed(() => String(route.query.patient_id ?? ''))

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
    if (!selectedId.value && res.data.length > 0) selectedId.value = res.data[0].id
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

async function loadQueue() {
  if (!canRvgRead.value) return
  queueLoading.value = true
  actionError.value = null
  try {
    const res = await fetchImports('pending')
    queue.value = res.data
    queueTotal.value = res.total
  } catch {
    actionError.value = t('imagingViewer.rvg.loadFailed')
  } finally {
    queueLoading.value = false
  }
}

async function scanNow() {
  scanning.value = true
  actionError.value = null
  try {
    await triggerScan()
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
    <h1 class="text-xl font-semibold">
      {{ t('imagingViewer.list.title') }}
    </h1>

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
          <p class="text-sm text-gray-500">
            {{ s.study_uid }}
          </p>
        </UCard>
      </div>

      <StudyViewer
        v-if="selectedId && can(PERMISSIONS.imagingViewer.studies.read)"
        :study-id="selectedId"
      />
      <AnnotationPanel
        v-if="selectedId && can(PERMISSIONS.imagingViewer.studies.read)"
        :study-id="selectedId"
      />
    </template>

    <UCard v-if="canRvgRead">
      <template #header>
        <div class="flex items-center justify-between">
          <span class="font-medium">{{ t('imagingViewer.rvg.title', { total: queueTotal }) }}</span>
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
            <p class="text-xs text-gray-500">
              {{ suggestionLabel(row) }}
            </p>
          </div>
          <div
            v-if="canRvgWrite"
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
