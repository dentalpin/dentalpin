<script setup lang="ts">
import { useImagingAi, type AiJob } from '../../composables/useImagingAi'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: 'auth' })

const { t } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const { fetchJobs } = useImagingAi()

const jobs = ref<AiJob[]>([])
const total = ref(0)
const loading = ref(false)
const patientId = computed(() => String(route.query.patient_id ?? ''))

async function load() {
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

onMounted(load)
watch(patientId, load)

const canQueue = computed(() => can(PERMISSIONS.imagingAi.jobs.write))

function statusColor(s: string) {
  if (s === 'done') return 'success'
  if (s === 'failed') return 'error'
  if (s === 'running') return 'info'
  return 'neutral'
}
</script>

<template>
  <div class="flex flex-col gap-4 p-4">
    <h1 class="text-xl font-semibold">
      {{ t('imagingAi.list.title') }}
    </h1>

    <UAlert
      v-if="!patientId"
      color="info"
      :title="t('imagingAi.list.noPatient')"
      :description="t('imagingAi.list.noPatientHint')"
    />

    <template v-else>
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
          <template #footer>
            <UBadge :color="statusColor(j.status)">
              {{ t(`imagingAi.status.${j.status}`) }}
            </UBadge>
          </template>
        </UCard>
      </div>

      <p
        v-if="canQueue"
        class="text-xs text-gray-500"
      >
        {{ t('imagingAi.list.queueHint') }}
      </p>
      <p class="text-xs text-gray-500">
        {{ t('imagingAi.list.visualizationNote') }}
      </p>
    </template>
  </div>
</template>
