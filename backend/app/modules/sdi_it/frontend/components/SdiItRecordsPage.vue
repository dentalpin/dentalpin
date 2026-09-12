<script setup lang="ts">
import { useSdiIt, SDI_STATES, fmtWhen, type SdiRecord } from '../composables/useSdiIt'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { fetchRecords, downloadXml, markExported, requeue, importReceipt, processNow, fetchSettings } = useSdiIt()

const records = ref<SdiRecord[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)
const stateFilter = ref<typeof SDI_STATES[number] | null>(null)
const transport = ref<'manual' | 'pec'>('manual')
const receiptXml = ref('')
const receiptFileName = ref('')
const importing = ref(false)

const stateOptions = computed(() => [
  { value: null, label: t('sdi_it.records.allStates') },
  ...SDI_STATES.map(s => ({ value: s, label: t(`sdi_it.state.${s}`) }))
])

const stateColor: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  pending: 'neutral',
  exported: 'info',
  delivered: 'success',
  undeliverable: 'warning',
  rejected: 'error',
  failed: 'error'
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

onMounted(async () => {
  try {
    transport.value = (await fetchSettings()).transport
  } catch {
    // settings.read may be missing for this role; the list still loads
  }
  await load()
})
watch([page, stateFilter], load)

async function act(fn: () => Promise<unknown>, okKey: string) {
  try {
    await fn()
    toast.add({ title: t(okKey), color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sdi_it.panel.actionFailed')), color: 'error' })
  }
}

async function onReceiptFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  receiptFileName.value = file.name
  receiptXml.value = await file.text()
}

async function onImportReceipt() {
  if (!receiptXml.value.trim()) return
  importing.value = true
  try {
    const res = await importReceipt(receiptXml.value, receiptFileName.value || undefined)
    toast.add({ title: t('sdi_it.panel.receiptImported'), description: `${res.receipt_type} → ${t(`sdi_it.state.${res.state}`)}`, color: 'success' })
    receiptXml.value = ''
    receiptFileName.value = ''
    await load()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sdi_it.panel.actionFailed')), color: 'error' })
  } finally {
    importing.value = false
  }
}

async function onProcessNow() {
  await act(async () => {
    const c = await processNow()
    toast.add({ title: t('sdi_it.records.processed', c), color: 'success' })
  }, 'sdi_it.records.processedTitle')
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between gap-2 flex-wrap">
      <div>
        <h2 class="text-lg font-semibold">
          {{ t('sdi_it.records.title') }}
        </h2>
        <p class="text-sm text-gray-500">
          {{ t('sdi_it.records.description') }}
        </p>
      </div>
      <div class="flex gap-2">
        <USelect
          v-model="stateFilter"
          :items="stateOptions"
          value-key="value"
          label-key="label"
          class="w-48"
        />
        <UButton
          v-if="transport === 'pec' && can(PERMISSIONS.sdiIt.recordsManage)"
          variant="outline"
          icon="i-lucide-send"
          @click="onProcessNow"
        >
          {{ t('sdi_it.records.processNow') }}
        </UButton>
      </div>
    </div>

    <UCard v-if="can(PERMISSIONS.sdiIt.recordsManage)">
      <template #header>
        <span class="font-medium">{{ t('sdi_it.panel.importReceipt') }}</span>
      </template>
      <div class="space-y-2">
        <p class="text-xs text-subtle">
          {{ t('sdi_it.panel.receiptHelp') }}
        </p>
        <input
          type="file"
          accept=".xml,text/xml,application/xml"
          class="text-xs"
          @change="onReceiptFile"
        >
        <UTextarea
          v-model="receiptXml"
          :rows="3"
          class="w-full font-mono text-xs"
        />
        <UButton
          size="xs"
          icon="i-lucide-check"
          :disabled="!receiptXml.trim()"
          :loading="importing"
          @click="onImportReceipt"
        >
          {{ t('sdi_it.panel.importReceipt') }}
        </UButton>
      </div>
    </UCard>

    <UCard>
      <USkeleton
        v-if="loading"
        class="h-48 w-full"
      />
      <div
        v-else-if="!records.length"
        class="text-sm text-gray-500 py-8 text-center"
      >
        {{ t('sdi_it.records.empty') }}
      </div>
      <div
        v-else
        class="overflow-x-auto"
      >
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-gray-500 border-b border-[var(--ui-border)]">
              <th class="py-2 pr-2">
                {{ t('sdi_it.records.invoice') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sdi_it.records.recipient') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sdi_it.records.file') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sdi_it.records.state') }}
              </th>
              <th class="py-2 pr-2">
                {{ t('sdi_it.records.receipt') }}
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
                  {{ r.tipo_documento }} · {{ r.invoice_number }}
                </div>
                <div class="text-xs text-gray-500">
                  {{ r.issue_date }} · {{ r.gross_amount }} EUR
                </div>
              </td>
              <td class="py-2 pr-2">
                <div>{{ r.recipient_name }}</div>
                <div class="text-xs text-gray-500 font-mono">
                  {{ r.recipient_tax_id }} · {{ r.codice_destinatario }}
                </div>
              </td>
              <td class="py-2 pr-2 font-mono text-xs break-all">
                {{ r.file_name }}
                <div
                  v-if="r.transport"
                  class="text-gray-500"
                >
                  {{ t(`sdi_it.transport.${r.transport}`) }}
                </div>
              </td>
              <td class="py-2 pr-2">
                <UBadge
                  :color="stateColor[r.state] ?? 'neutral'"
                  variant="subtle"
                >
                  {{ t(`sdi_it.state.${r.state}`) }}
                </UBadge>
                <div
                  v-if="r.error_message"
                  class="text-xs text-red-500 mt-0.5 max-w-xs break-words"
                >
                  <span v-if="r.error_code">{{ r.error_code }}: </span>{{ r.error_message }}
                </div>
              </td>
              <td class="py-2 pr-2 text-xs">
                <template v-if="r.receipt_type">
                  {{ r.receipt_type }}<span v-if="r.sdi_identifier"> · {{ r.sdi_identifier }}</span>
                  <div class="text-gray-500">
                    {{ fmtWhen(r.receipt_at) }}
                  </div>
                </template>
                <span v-else>—</span>
              </td>
              <td class="py-2 text-right whitespace-nowrap">
                <UButton
                  size="xs"
                  variant="ghost"
                  icon="i-lucide-download"
                  :title="t('sdi_it.panel.download')"
                  @click="act(() => downloadXml(r), 'sdi_it.panel.downloaded')"
                />
                <UButton
                  v-if="r.state === 'pending' && can(PERMISSIONS.sdiIt.recordsManage)"
                  size="xs"
                  variant="soft"
                  icon="i-lucide-upload"
                  @click="act(() => markExported(r.id), 'sdi_it.panel.markedExported')"
                >
                  {{ t('sdi_it.panel.markExported') }}
                </UButton>
                <UButton
                  v-if="r.state === 'rejected' && can(PERMISSIONS.sdiIt.recordsManage)"
                  size="xs"
                  color="warning"
                  variant="soft"
                  icon="i-lucide-rotate-ccw"
                  @click="act(() => requeue(r.id), 'sdi_it.panel.requeued')"
                >
                  {{ t('sdi_it.panel.requeue') }}
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
