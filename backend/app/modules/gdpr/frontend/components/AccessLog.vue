<script setup lang="ts">
import type { PaginatedResponse } from '~~/app/types'

type AuditEntry = {
  id: string
  user_id: string
  user_name: string | null
  patient_id: string
  patient_name: string | null
  action: string
  resource: string
  occurred_at: string
  client_ip: string | null
}

const props = defineProps<{
  patientId?: string
  userId?: string
}>()
const { t, locale } = useI18n()
const api = useApi()
const { currentClinic } = useClinic()
const page = ref(1)
const pageSize = 25
const start = ref('')
const end = ref('')
const total = ref(0)
const entries = ref<AuditEntry[]>([])
const loading = ref(false)
const exporting = ref(false)
const loadError = ref(false)
const exportError = ref(false)
const invalidDates = computed(() => Boolean(start.value && end.value && start.value > end.value))
const target = computed(() => props.patientId
  ? { patient_id: props.patientId }
  : { user_id: props.userId })
const filter = computed(() => ({
  ...target.value,
  start: start.value || undefined,
  end: end.value || undefined
}))
const formatter = computed(() => new Intl.DateTimeFormat(locale.value, {
  dateStyle: 'short',
  timeStyle: 'medium',
  timeZone: currentClinic.value?.timezone || 'UTC'
}))

watch(filter, () => {
  page.value = 1
  exportError.value = false
}, { flush: 'sync' })

watch([filter, page], async (_, __, onCleanup) => {
  entries.value = []
  total.value = 0
  loadError.value = false
  loading.value = false
  if ((!props.patientId && !props.userId) || invalidDates.value) return
  const controller = new AbortController()
  onCleanup(() => controller.abort())
  loading.value = true
  try {
    const result = await api.get<PaginatedResponse<AuditEntry>>('/api/v1/gdpr/access-log', {
      query: { ...filter.value, page: page.value, page_size: pageSize },
      signal: controller.signal,
      errorToast: false
    })
    if (!controller.signal.aborted) {
      entries.value = result.data
      total.value = result.total
    }
  } catch {
    if (!controller.signal.aborted) loadError.value = true
  } finally {
    if (!controller.signal.aborted) loading.value = false
  }
}, { immediate: true })

async function download() {
  if (!start.value || !end.value || invalidDates.value || exporting.value) return
  exportError.value = false
  exporting.value = true
  try {
    const params = new URLSearchParams({ start: start.value, end: end.value })
    if (props.patientId) params.set('patient_id', props.patientId)
    else if (props.userId) params.set('user_id', props.userId)
    const response = await api.raw(`/api/v1/gdpr/access-log/csv?${params}`)
    if (!response.ok) throw new Error('CSV request failed')
    const url = URL.createObjectURL(await response.blob())
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'patient-access-log.csv'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    exportError.value = true
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-end gap-3">
      <UFormField :label="t('gdprAccess.from')">
        <UInput
          v-model="start"
          type="date"
        />
      </UFormField>
      <UFormField
        :label="t('gdprAccess.to')"
        :error="invalidDates ? t('gdprAccess.invalidDates') : undefined"
      >
        <UInput
          v-model="end"
          type="date"
        />
      </UFormField>
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-download"
        :disabled="!start || !end || invalidDates"
        :loading="exporting"
        @click="download"
      >
        {{ t('gdprAccess.csv') }}
      </UButton>
    </div>
    <p
      v-if="exportError"
      role="alert"
      class="text-sm text-error"
    >
      {{ t('gdprAccess.exportError') }}
    </p>
    <p
      v-if="loading"
      role="status"
      class="text-sm text-muted"
    >
      {{ t('gdprAccess.loading') }}
    </p>
    <p
      v-else-if="loadError"
      role="alert"
      class="text-sm text-error"
    >
      {{ t('gdprAccess.loadError') }}
    </p>
    <p
      v-else-if="!entries.length && !invalidDates"
      class="text-sm text-muted"
    >
      {{ t('gdprAccess.empty') }}
    </p>
    <div
      v-if="entries.length"
      class="overflow-x-auto"
    >
      <table class="w-full text-sm">
        <thead class="text-left text-muted">
          <tr class="border-b border-default">
            <th
              scope="col"
              class="p-2"
            >
              {{ t('gdprAccess.when') }}
            </th>
            <th
              scope="col"
              class="p-2"
            >
              {{ t(patientId ? 'gdprAccess.staff' : 'gdprAccess.patient') }}
            </th>
            <th
              scope="col"
              class="p-2"
            >
              {{ t('gdprAccess.action') }}
            </th>
            <th
              scope="col"
              class="p-2"
            >
              {{ t('gdprAccess.resource') }}
            </th>
            <th
              scope="col"
              class="p-2"
            >
              {{ t('gdprAccess.ip') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="entry in entries"
            :key="entry.id"
            class="border-b border-default"
          >
            <td class="whitespace-nowrap p-2">
              <time :datetime="entry.occurred_at">{{ formatter.format(new Date(entry.occurred_at)) }}</time>
            </td>
            <td class="p-2">
              {{ patientId ? (entry.user_name || entry.user_id) : (entry.patient_name || entry.patient_id) }}
            </td>
            <td class="p-2">
              {{ t(`gdprAccess.actions.${entry.action}`, entry.action) }}
            </td>
            <td class="p-2">
              {{ t(`gdprAccess.resources.${entry.resource}`, entry.resource) }}
            </td>
            <td class="whitespace-nowrap p-2">
              {{ entry.client_ip || '—' }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <UPagination
      v-if="total > pageSize"
      v-model:page="page"
      :items-per-page="pageSize"
      :total="total"
    />
  </div>
</template>
