<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import type { Recall, RecallStatus, RecallReason, RecallPriority } from '../../composables/useRecalls'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const recallsApi = useRecalls()
const { can } = usePermissions()

if (!can(PERMISSIONS.recalls.read)) {
  await navigateTo('/')
}

// Sentinel for "Any" — Reka UI's SelectItem rejects empty-string
// values (reserves them for the placeholder state). We round-trip
// this token through the dropdown and normalise to undefined on the
// API call. Same pattern used by `AppointmentModal` for unassigned
// cabinets (#51).
const ANY = '__any__'

// Filters from query string.
const month = ref<string>(String(route.query.month ?? defaultMonthIso()))
const reason = ref<RecallReason | typeof ANY>((route.query.reason as RecallReason) ?? ANY)
const status = ref<RecallStatus | typeof ANY>((route.query.status as RecallStatus) ?? 'pending')
const priority = ref<RecallPriority | typeof ANY>((route.query.priority as RecallPriority) ?? ANY)
const overdue = ref<boolean>(route.query.overdue === 'true')
const patientId = ref<string | undefined>((route.query.patient_id as string) || undefined)

const stats = ref<{
  due_this_week: number
  due_this_month: number
  overdue: number
  scheduled_this_month: number
  completed_this_month: number
  conversion_rate: number
} | null>(null)

const items = ref<Recall[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const isLoading = ref(false)

function defaultMonthIso(): string {
  const today = new Date()
  return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`
}

const reasonOptions = computed(() => [
  { value: ANY, label: t('recalls.filters.any') },
  ...(['hygiene', 'checkup', 'ortho_review', 'implant_review', 'post_op', 'treatment_followup', 'other'] as RecallReason[]).map(r => ({
    value: r,
    label: t(`recalls.reasons.${r}`)
  }))
])

const statusOptions = computed(() => [
  { value: ANY, label: t('recalls.filters.any') },
  ...(['pending', 'contacted_no_answer', 'contacted_scheduled', 'contacted_declined', 'done', 'cancelled', 'needs_review'] as RecallStatus[]).map(s => ({
    value: s,
    label: t(`recalls.status.${s}`)
  }))
])

const priorityOptions = computed(() => [
  { value: ANY, label: t('recalls.filters.any') },
  ...(['low', 'normal', 'high'] as RecallPriority[]).map(p => ({
    value: p,
    label: t(`recalls.priority.${p}`)
  }))
])

async function load() {
  isLoading.value = true
  try {
    const filters: Record<string, unknown> = {
      month: month.value || undefined,
      reason: reason.value === ANY ? undefined : reason.value || undefined,
      status: status.value === ANY ? undefined : status.value || undefined,
      priority: priority.value === ANY ? undefined : priority.value || undefined,
      overdue: overdue.value || undefined,
      patient_id: patientId.value,
      page: page.value,
      page_size: pageSize.value
    }
    const [list, dash] = await Promise.all([
      recallsApi.list(filters),
      recallsApi.dashboardStats()
    ])
    items.value = list.data
    total.value = list.total
    stats.value = dash.data
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

watch([month, reason, status, priority, overdue, patientId], () => {
  page.value = 1
  router.replace({
    query: {
      ...(month.value ? { month: month.value } : {}),
      ...(reason.value && reason.value !== ANY ? { reason: reason.value } : {}),
      ...(status.value && status.value !== ANY ? { status: status.value } : {}),
      ...(priority.value && priority.value !== ANY ? { priority: priority.value } : {}),
      ...(overdue.value ? { overdue: 'true' } : {}),
      ...(patientId.value ? { patient_id: patientId.value } : {})
    }
  })
  load()
})

function onChanged(updated: Recall) {
  const idx = items.value.findIndex(r => r.id === updated.id)
  if (idx >= 0) items.value[idx] = { ...items.value[idx], ...updated }
  // Refresh stats on any state change.
  recallsApi.dashboardStats().then((res) => {
    stats.value = res.data
  }).catch(() => { /* ignore */ })
}

const conversionPct = computed(() => stats.value ? Math.round(stats.value.conversion_rate * 100) : 0)

const auth = useAuth()
const config = useRuntimeConfig()
const isExporting = ref(false)

async function downloadCsv() {
  if (isExporting.value) return
  isExporting.value = true
  try {
    const url = config.public.apiBaseUrl + recallsApi.exportCsvUrl({
      month: month.value || undefined,
      reason: reason.value === ANY ? undefined : reason.value || undefined,
      status: status.value === ANY ? undefined : status.value || undefined,
      priority: priority.value === ANY ? undefined : priority.value || undefined,
      overdue: overdue.value || undefined
    })
    const res = await fetch(url, {
      headers: auth.accessToken.value
        ? { Authorization: `Bearer ${auth.accessToken.value}` }
        : {}
    })
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = 'recalls.csv'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(blobUrl)
  } finally {
    isExporting.value = false
  }
}
</script>

<template>
  <div class="container mx-auto p-4 space-y-4">
    <header class="flex items-center justify-between gap-2 flex-wrap">
      <h1 class="text-h1">
        {{ t('recalls.callList') }}
      </h1>
      <UButton
        icon="i-lucide-download"
        size="sm"
        variant="soft"
        :loading="isExporting"
        @click="downloadCsv"
      >
        {{ t('recalls.actions.exportCsv') }}
      </UButton>
    </header>

    <section
      v-if="stats"
      class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center"
    >
      <UCard :ui="{ body: 'p-2' }">
        <div class="text-h2 tnum">
          {{ stats.due_this_week }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('recalls.counters.due_this_week') }}
        </div>
      </UCard>
      <UCard :ui="{ body: 'p-2' }">
        <div class="text-h2 tnum">
          {{ stats.overdue }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('recalls.counters.overdue') }}
        </div>
      </UCard>
      <UCard :ui="{ body: 'p-2' }">
        <div class="text-h2 tnum">
          {{ stats.scheduled_this_month }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('recalls.counters.scheduled_this_month') }}
        </div>
      </UCard>
      <UCard :ui="{ body: 'p-2' }">
        <div class="text-h2 tnum">
          {{ conversionPct }}%
        </div>
        <div class="text-caption text-subtle">
          {{ t('recalls.counters.conversion_rate') }}
        </div>
      </UCard>
    </section>

    <section class="grid grid-cols-2 sm:grid-cols-5 gap-2">
      <UFormField :label="t('recalls.filters.month')">
        <MonthPickerDropdown v-model="month" />
      </UFormField>
      <UFormField :label="t('recalls.filters.reason')">
        <USelectMenu
          v-model="reason"
          :items="reasonOptions"
          value-key="value"
          label-key="label"
        />
      </UFormField>
      <UFormField :label="t('recalls.filters.status')">
        <USelectMenu
          v-model="status"
          :items="statusOptions"
          value-key="value"
          label-key="label"
        />
      </UFormField>
      <UFormField :label="t('recalls.filters.priority')">
        <USelectMenu
          v-model="priority"
          :items="priorityOptions"
          value-key="value"
          label-key="label"
        />
      </UFormField>
      <UFormField :label="t('recalls.filters.overdue')">
        <USwitch v-model="overdue" />
      </UFormField>
    </section>

    <RecallList
      :items="items"
      :is-loading="isLoading"
      @changed="onChanged"
    />
  </div>
</template>
