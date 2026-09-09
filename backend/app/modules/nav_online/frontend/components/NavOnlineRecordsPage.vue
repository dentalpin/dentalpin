<script setup lang="ts">
import { useNavOnline, type NavRecord } from '../composables/useNavOnline'
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { fetchRecords, retryRecord, processNow } = useNavOnline()

const records = ref<NavRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const stateFilter = ref<string | null>(null)

const stateOptions = computed(() => [
  { value: null, label: t('nav_online.records.allStates') },
  ...['pending', 'sending', 'sent', 'done', 'rejected', 'failed', 'aborted'].map(s => ({
    value: s,
    label: t(`nav_online.state.${s}`)
  }))
])

const stateColor: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  pending: 'neutral',
  sending: 'info',
  sent: 'info',
  done: 'success',
  rejected: 'error',
  failed: 'warning',
  aborted: 'error'
}

async function load() {
  loading.value = true
  try {
    const res = await fetchRecords({ page: page.value, page_size: pageSize, state: stateFilter.value || undefined })
    records.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch([page, stateFilter], load)

async function onRetry(r: NavRecord) {
  try {
    await retryRecord(r.id)
    toast.add({ title: t('nav_online.records.requeued'), color: 'success' })
    await load()
  } catch {
    // useApi toasts 400s itself.
  }
}

async function onProcessNow() {
  try {
    const c = await processNow()
    toast.add({ title: t('nav_online.records.processed', c), color: 'success' })
    await load()
  } catch {
    // toasted by useApi
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <div>
        <h2 class="text-lg font-semibold">
          {{ t('nav_online.records.title') }}
        </h2>
        <p class="text-sm text-gray-500">
          {{ t('nav_online.records.description') }}
        </p>
      </div>
      <div class="flex gap-2">
        <USelect
          v-model="stateFilter"
          :items="stateOptions"
          value-key="value"
          label-key="label"
          class="w-44"
        />
        <UButton
          v-if="can(PERMISSIONS.navOnline.queueManage)"
          variant="outline"
          icon="i-lucide-send"
          @click="onProcessNow"
        >
          {{ t('nav_online.records.processNow') }}
        </UButton>
      </div>
    </div>

    <UCard>
      <USkeleton
        v-if="loading"
        class="h-48 w-full"
      />
      <div
        v-else-if="!records.length"
        class="text-sm text-gray-500 py-8 text-center"
      >
        {{ t('nav_online.records.empty') }}
      </div>
      <table
        v-else
        class="w-full text-sm"
      >
        <thead>
          <tr class="text-left text-gray-500 border-b border-[var(--ui-border)]">
            <th class="py-2 pr-2">
              {{ t('nav_online.records.invoice') }}
            </th>
            <th class="py-2 pr-2">
              {{ t('nav_online.records.operation') }}
            </th>
            <th class="py-2 pr-2">
              {{ t('nav_online.records.state') }}
            </th>
            <th class="py-2 pr-2">
              {{ t('nav_online.records.transaction') }}
            </th>
            <th class="py-2 pr-2">
              {{ t('nav_online.records.error') }}
            </th>
            <th class="py-2" />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="r in records"
            :key="r.id"
            class="border-b border-[var(--ui-border)] last:border-0 align-top"
          >
            <td class="py-2 pr-2 whitespace-nowrap">
              <div class="font-medium">
                {{ r.invoice_number }}
              </div>
              <div class="text-xs text-gray-500">
                {{ r.issue_date }} · {{ r.gross_amount }} HUF
              </div>
            </td>
            <td class="py-2 pr-2">
              {{ r.operation }}
            </td>
            <td class="py-2 pr-2">
              <UBadge
                :color="stateColor[r.state] ?? 'neutral'"
                variant="subtle"
              >
                {{ t(`nav_online.state.${r.state}`) }}
              </UBadge>
              <div
                v-if="r.nav_status"
                class="text-xs text-gray-500 mt-0.5"
              >
                {{ r.nav_status }}
              </div>
            </td>
            <td class="py-2 pr-2 font-mono text-xs break-all">
              {{ r.transaction_id ?? '—' }}
            </td>
            <td class="py-2 pr-2 text-xs text-red-500 break-words max-w-xs">
              <span v-if="r.error_code">{{ r.error_code }}: </span>{{ r.error_message ?? '' }}
            </td>
            <td class="py-2 text-right">
              <UButton
                v-if="['rejected', 'failed', 'aborted', 'sending'].includes(r.state) && can(PERMISSIONS.navOnline.queueManage)"
                size="xs"
                variant="soft"
                icon="i-lucide-rotate-ccw"
                @click="onRetry(r)"
              >
                {{ t('nav_online.records.retry') }}
              </UButton>
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
