<script setup lang="ts">
import { useSistemaTs, fmtWhen, fmtDate, TS_STATES, type TsDocument } from '../composables/useSistemaTs'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { fetchDocuments, retry, processNow } = useSistemaTs()

const docs = ref<TsDocument[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const stateFilter = ref<typeof TS_STATES[number] | null>(null)
const year = ref<number>(new Date().getFullYear())

const stateOptions = computed(() => [
  { value: null, label: t('sistema_ts.documents.allStates') },
  ...TS_STATES.map(s => ({ value: s, label: t(`sistema_ts.state.${s}`) }))
])
const yearOptions = computed(() => {
  const y = new Date().getFullYear()
  return [y, y - 1, y - 2].map(v => ({ value: v, label: String(v) }))
})

const stateColor: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  pending: 'neutral',
  sending: 'info',
  accepted: 'success',
  accepted_with_warnings: 'warning',
  rejected: 'error',
  failed: 'error'
}

async function load() {
  loading.value = true
  try {
    const res = await fetchDocuments({ page: page.value, page_size: pageSize, state: stateFilter.value || undefined, year: year.value })
    docs.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(page, load)
watch([stateFilter, year], () => {
  if (page.value !== 1) page.value = 1
  else load()
})

async function onRetry(d: TsDocument) {
  try {
    await retry(d.id)
    toast.add({ title: t('sistema_ts.documents.requeued'), color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sistema_ts.documents.actionFailed')), color: 'error' })
  }
}

async function onProcessNow() {
  try {
    const c = await processNow()
    toast.add({ title: t('sistema_ts.documents.processed', c), color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sistema_ts.documents.actionFailed')), color: 'error' })
  }
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <div>
        <h2 class="text-lg font-semibold">
          {{ t('sistema_ts.documents.title') }}
        </h2>
        <p class="text-sm text-gray-500">
          {{ t('sistema_ts.documents.description') }}
        </p>
      </div>
      <div class="flex gap-2">
        <USelect
          v-model="year"
          :items="yearOptions"
          value-key="value"
          label-key="label"
          class="w-28"
        />
        <USelect
          v-model="stateFilter"
          :items="stateOptions"
          value-key="value"
          label-key="label"
          class="w-52"
        />
        <UButton
          v-if="can(PERMISSIONS.sistemaTs.documentsManage)"
          variant="outline"
          icon="i-lucide-send"
          @click="onProcessNow"
        >
          {{ t('sistema_ts.documents.processNow') }}
        </UButton>
      </div>
    </div>

    <UCard>
      <USkeleton
        v-if="loading"
        class="h-48 w-full"
      />
      <div
        v-else-if="!docs.length"
        class="text-sm text-gray-500 py-8 text-center"
      >
        {{ t('sistema_ts.documents.empty') }}
      </div>
      <div
        v-else
        class="overflow-x-auto"
      >
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-gray-500 border-b border-[var(--ui-border)]">
              <th class="py-2 pr-2">
                {{ t('sistema_ts.documents.document') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sistema_ts.documents.operation') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sistema_ts.documents.state') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sistema_ts.documents.protocollo') }}
              </th>
              <th class="py-2" />
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="d in docs"
              :key="d.id"
              class="border-b border-[var(--ui-border)] last:border-0 align-top"
            >
              <td class="py-2 pr-2 whitespace-nowrap">
                <div class="font-medium">
                  {{ d.num_documento }}
                </div>
                <div class="text-xs text-gray-500">
                  {{ fmtDate(d.data_emissione) }} · {{ d.total_amount }} EUR · {{ d.pagamento_tracciato === 'SI' ? t('sistema_ts.documents.traceable') : t('sistema_ts.documents.cash') }}
                  <span
                    v-if="d.flag_opposizione"
                    class="text-amber-600"
                  > · {{ t('sistema_ts.opposition.opposed') }}</span>
                </div>
              </td>
              <td class="py-2 pr-2">
                {{ t(`sistema_ts.operation.${d.operation}`) }}
              </td>
              <td class="py-2 pr-2">
                <UBadge
                  :color="stateColor[d.state] ?? 'neutral'"
                  variant="subtle"
                >
                  {{ t(`sistema_ts.state.${d.state}`) }}
                </UBadge>
                <div
                  v-if="d.error_message"
                  class="text-xs text-red-500 mt-0.5 max-w-xs break-words"
                >
                  {{ d.error_message }}
                </div>
              </td>
              <td class="py-2 pr-2 font-mono text-xs">
                {{ d.protocollo ?? '—' }}
                <div class="text-gray-500 font-sans">
                  {{ fmtWhen(d.finished_at ?? d.sent_at) }}
                </div>
              </td>
              <td class="py-2 text-right whitespace-nowrap">
                <UButton
                  v-if="['rejected', 'failed'].includes(d.state) && can(PERMISSIONS.sistemaTs.documentsManage)"
                  size="xs"
                  variant="soft"
                  icon="i-lucide-rotate-ccw"
                  @click="onRetry(d)"
                >
                  {{ t('sistema_ts.documents.retry') }}
                </UButton>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
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
