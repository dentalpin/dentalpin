<script setup lang="ts">
import { useImagingAi, type AiJob, type DicomDocument, type PatientOption } from '../../composables/useImagingAi'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail, errorMessage } from '~~/app/utils/error'

definePageMeta({ middleware: 'auth' })

const { t } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const router = useRouter()
const { queueJob, confirmJob, cancelJob, fetchJobs, fetchDicomDocuments, searchPatients } = useImagingAi()

const jobs = ref<AiJob[]>([])
const total = ref(0)
const loading = ref(false)
const queueing = ref(false)
const queueError = ref('')

const patientId = ref(String(route.query.patient_id ?? ''))
const selectedPatient = ref<(PatientOption & { label: string }) | null>(null)
const patientOptions = ref<(PatientOption & { label: string })[]>([])
const patientSearch = ref('')
const searching = ref(false)

const dicomDocs = ref<DicomDocument[]>([])
const loadingDocs = ref(false)
const selectedDocs = ref<string[]>([])
const backend = ref('pano')

const canQueue = computed(() => can(PERMISSIONS.imagingAi.jobs.write))
const canReadPatients = computed(() => can(PERMISSIONS.patients.read))

async function runPatientSearch() {
  searching.value = true
  try {
    const found = await searchPatients(patientSearch.value)
    patientOptions.value = found.map(p => ({ ...p, label: `${p.first_name} ${p.last_name}` }))
  } finally {
    searching.value = false
  }
}

async function pickPatient(p: (PatientOption & { label: string }) | null) {
  if (!p) return
  patientId.value = p.id
  selectedDocs.value = []
  await router.replace({ query: { ...route.query, patient_id: p.id } })
  await Promise.all([loadJobs(), loadDocs()])
}

async function loadJobs() {
  if (!patientId.value) return
  loading.value = true
  try {
    const res = await fetchJobs(patientId.value)
    jobs.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

async function loadDocs() {
  if (!patientId.value) return
  loadingDocs.value = true
  try {
    dicomDocs.value = await fetchDicomDocuments(patientId.value)
  } finally {
    loadingDocs.value = false
  }
}

async function submitQueue() {
  if (!patientId.value || selectedDocs.value.length === 0) return
  queueing.value = true
  queueError.value = ''
  try {
    await queueJob(patientId.value, {
      document_id: selectedDocs.value[0]!,
      series_document_ids: selectedDocs.value.slice(1),
      backend: backend.value
    })
    selectedDocs.value = []
    await loadJobs()
  } catch (e: unknown) {
    queueError.value = errorDetail(e) ?? errorMessage(e, String(e))
  } finally {
    queueing.value = false
  }
}

async function onConfirm(j: AiJob) {
  queueError.value = ''
  try {
    await confirmJob(j.id)
    await loadJobs()
  } catch (e: unknown) {
    queueError.value = errorDetail(e) ?? errorMessage(e, String(e))
  }
}

async function onCancel(j: AiJob) {
  queueError.value = ''
  try {
    await cancelJob(j.id)
    await loadJobs()
  } catch (e: unknown) {
    queueError.value = errorDetail(e) ?? errorMessage(e, String(e))
  }
}

function canConfirm(j: AiJob) {
  return j.status === 'proposed' || (j.status === 'done' && j.review_status === 'pending_review')
}

function canCancel(j: AiJob) {
  return j.status === 'proposed' || j.status === 'queued'
}

function statusColor(s: string) {
  if (s === 'done') return 'success'
  if (s === 'failed') return 'error'
  if (s === 'running') return 'info'
  if (s === 'proposed') return 'warning'
  return 'neutral'
}

onMounted(async () => {
  if (patientId.value) {
    await Promise.all([loadJobs(), loadDocs()])
  }
})
</script>

<template>
  <div class="flex flex-col gap-4 p-4">
    <h1 class="text-xl font-semibold">
      {{ t('imagingAi.list.title') }}
    </h1>

    <UCard v-if="canReadPatients">
      <template #header>
        <span class="font-medium">{{ t('imagingAi.queue.patient') }}</span>
      </template>
      <div class="flex flex-wrap items-end gap-2">
        <UFormField :label="t('imagingAi.queue.patient')">
          <UInput
            v-model="patientSearch"
            :placeholder="t('imagingAi.queue.searchPatients')"
          />
        </UFormField>
        <UButton
          :loading="searching"
          @click="runPatientSearch"
        >
          {{ t('imagingAi.queue.search') }}
        </UButton>
      </div>
      <USelectMenu
        v-model="selectedPatient"
        :items="patientOptions"
        :loading="searching"
        :placeholder="t('imagingAi.queue.searchPatients')"
        label-key="label"
        searchable
        @update:model-value="pickPatient"
      />
    </UCard>
    <UAlert
      v-else-if="!patientId"
      color="info"
      :title="t('imagingAi.list.noPatient')"
      :description="t('imagingAi.list.noPatientHint')"
    />

    <template v-if="patientId">
      <UCard v-if="canQueue">
        <template #header>
          <span class="font-medium">{{ t('imagingAi.queue.title') }}</span>
        </template>
        <USkeleton
          v-if="loadingDocs"
          class="h-16 w-full"
        />
        <UAlert
          v-else-if="dicomDocs.length === 0"
          color="info"
          :title="t('imagingAi.queue.noDicom')"
        />
        <div
          v-else
          class="flex flex-col gap-2"
        >
          <UCheckbox
            v-for="d in dicomDocs"
            :key="d.id"
            :model-value="selectedDocs.includes(d.id)"
            :label="d.original_filename"
            @update:model-value="(v: boolean) => {
              selectedDocs = v
                ? [...selectedDocs, d.id]
                : selectedDocs.filter(x => x !== d.id)
            }"
          />
          <div class="flex flex-wrap items-end gap-2">
            <UFormField :label="t('imagingAi.queue.backend')">
              <USelect
                v-model="backend"
                :items="[
                  { label: t('imagingAi.backends.pano'), value: 'pano' },
                  { label: t('imagingAi.backends.nnunet'), value: 'nnunet' }
                ]"
                value-key="value"
              />
            </UFormField>
            <UButton
              :loading="queueing"
              :disabled="selectedDocs.length === 0"
              @click="submitQueue"
            >
              {{ t('imagingAi.queue.submit') }}
            </UButton>
          </div>
          <p class="text-xs text-gray-500">
            {{ t('imagingAi.queue.seriesHint') }}
          </p>
          <p class="text-xs text-gray-500">
            {{ t('imagingAi.list.queueHint') }}
          </p>
          <UAlert
            v-if="queueError"
            color="error"
            :title="queueError"
          />
        </div>
      </UCard>

      <USkeleton
        v-if="loading"
        class="h-24 w-full"
      />
      <UAlert
        v-else-if="jobs.length === 0"
        color="info"
        :title="t('imagingAi.list.empty')"
      />
      <div
        v-else
        class="grid grid-cols-1 gap-4 lg:grid-cols-3"
      >
        <UCard
          v-for="j in jobs"
          :key="j.id"
        >
          <template #header>
            <span class="font-medium">{{ j.backend }}</span>
          </template>
          <p class="text-sm text-gray-500">
            {{ j.model_id }} {{ j.model_version }}
          </p>
          <p
            v-if="j.error"
            class="mt-1 text-sm text-red-600"
          >
            {{ j.error }}
          </p>
          <p
            v-if="j.log_excerpt"
            class="mt-1 text-xs text-gray-400"
          >
            {{ j.log_excerpt.slice(-300) }}
          </p>
          <div
            v-if="j.artifact_document_ids.length > 0"
            class="mt-2 flex flex-col gap-1"
          >
            <span class="text-xs font-medium">{{ t('imagingAi.job.artifacts') }}</span>
            <a
              v-for="a in j.artifact_document_ids"
              :key="a"
              class="text-xs text-primary underline"
              :href="`/api/v1/media/documents/${a}/download`"
            >
              {{ a }}
            </a>
          </div>
          <template #footer>
            <div class="flex flex-wrap items-center gap-2">
              <UBadge :color="statusColor(j.status)">
                {{ t(`imagingAi.status.${j.status}`) }}
              </UBadge>
              <UBadge
                v-if="j.status === 'done'"
                color="warning"
              >
                {{ t(`imagingAi.review.${j.review_status}`) }}
              </UBadge>
              <UButton
                v-if="canQueue && canConfirm(j)"
                size="xs"
                @click="onConfirm(j)"
              >
                {{ t('imagingAi.job.confirm') }}
              </UButton>
              <UButton
                v-if="canQueue && canCancel(j)"
                size="xs"
                variant="soft"
                @click="onCancel(j)"
              >
                {{ t('imagingAi.job.cancel') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </div>

      <p class="text-xs text-gray-500">
        {{ t('imagingAi.list.visualizationNote') }}
      </p>
    </template>
  </div>
</template>
