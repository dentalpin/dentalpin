<script setup lang="ts">
import { useTelephony, type CallLog } from '../../composables/useTelephony'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ middleware: 'auth' })

const { t } = useI18n()
const { can } = usePermissions()
const { fetchCalls, fetchActiveCalls } = useTelephony()

const calls = ref<CallLog[]>([])
const active = ref<CallLog[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const statusFilter = ref<string | undefined>(undefined)

const statusOptions = computed(() => [
  { value: undefined, label: t('telephony.calls.allStatuses') },
  { value: 'ringing', label: t('telephony.calls.status.ringing') },
  { value: 'answered', label: t('telephony.calls.status.answered') },
  { value: 'ended', label: t('telephony.calls.status.ended') },
  { value: 'missed', label: t('telephony.calls.status.missed') }
])

async function load() {
  loading.value = true
  try {
    const res = await fetchCalls({ page: page.value, page_size: pageSize, status: statusFilter.value })
    calls.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

let timer: ReturnType<typeof setInterval> | undefined
async function pollActive() {
  try {
    active.value = await fetchActiveCalls()
  } catch {
    // Background poll — stay quiet.
  }
}

onMounted(() => {
  load()
  pollActive()
  timer = setInterval(pollActive, 15000)
})
onUnmounted(() => timer && clearInterval(timer))

watch([page, statusFilter], load)

function durationLabel(c: CallLog): string {
  if (c.duration_seconds == null) return '—'
  const m = Math.floor(c.duration_seconds / 60)
  const s = c.duration_seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

const statusColor: Record<string, 'success' | 'warning' | 'error' | 'neutral'> = {
  ringing: 'warning',
  answered: 'success',
  ended: 'neutral',
  missed: 'error'
}
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">
        {{ t('telephony.calls.title') }}
      </h1>
      <USelect
        v-model="statusFilter"
        :items="statusOptions"
        value-key="value"
        label-key="label"
        class="w-44"
      />
    </div>

    <!-- Live calls banner -->
    <UAlert
      v-for="c in active"
      :key="c.id"
      icon="i-lucide-phone-incoming"
      :color="c.status === 'ringing' ? 'warning' : 'success'"
      :title="c.patient_name || t('telephony.calls.unknownCaller')"
      :description="`${c.from_number} — ${t(`telephony.calls.status.${c.status}`)}`"
    >
      <template #actions>
        <UButton
          v-if="c.patient_id"
          size="xs"
          :to="`/patients/${c.patient_id}`"
        >
          {{ t('telephony.calls.openRecord') }}
        </UButton>
        <UButton
          v-else
          size="xs"
          variant="outline"
          :to="`/patients?phone=${encodeURIComponent(c.from_number)}`"
        >
          {{ t('telephony.calls.searchPatient') }}
        </UButton>
      </template>
    </UAlert>

    <UCard>
      <USkeleton
        v-if="loading"
        class="h-48 w-full"
      />
      <div
        v-else-if="!calls.length"
        class="text-sm text-gray-500 py-8 text-center"
      >
        {{ t('telephony.calls.empty') }}
      </div>
      <table
        v-else
        class="w-full text-sm"
      >
        <thead>
          <tr class="text-start text-gray-500 border-b border-[var(--ui-border)]">
            <th class="py-2 pe-2">
              {{ t('telephony.calls.when') }}
            </th>
            <th class="py-2 pe-2">
              {{ t('telephony.calls.caller') }}
            </th>
            <th class="py-2 pe-2">
              {{ t('telephony.calls.number') }}
            </th>
            <th class="py-2 pe-2">
              {{ t('telephony.calls.statusCol') }}
            </th>
            <th class="py-2 pe-2">
              {{ t('telephony.calls.duration') }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="c in calls"
            :key="c.id"
            class="border-b border-[var(--ui-border)] last:border-0"
          >
            <td class="py-2 pe-2 whitespace-nowrap">
              {{ new Date(c.started_at || c.created_at).toLocaleString() }}
            </td>
            <td class="py-2 pe-2">
              <NuxtLink
                v-if="c.patient_id && can(PERMISSIONS.patients.read)"
                :to="`/patients/${c.patient_id}`"
                class="text-[var(--ui-primary)] hover:underline"
              >
                {{ c.patient_name }}
              </NuxtLink>
              <span
                v-else
                class="text-gray-500"
              >{{ c.patient_name || t('telephony.calls.unknownCaller') }}</span>
            </td>
            <td class="py-2 pe-2 font-mono text-xs">
              {{ c.from_number }}
            </td>
            <td class="py-2 pe-2">
              <UBadge
                :color="statusColor[c.status] ?? 'neutral'"
                variant="subtle"
              >
                {{ t(`telephony.calls.status.${c.status}`) }}
              </UBadge>
            </td>
            <td class="py-2 pe-2">
              {{ durationLabel(c) }}
            </td>
          </tr>
        </tbody>
      </table>
      <template
        v-if="total > pageSize"
        #footer
      >
        <UPagination
          v-model:page="page"
          :total="total"
          :items-per-page="pageSize"
        />
      </template>
    </UCard>
  </div>
</template>
