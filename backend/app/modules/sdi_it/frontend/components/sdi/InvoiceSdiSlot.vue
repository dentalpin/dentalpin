<script setup lang="ts">
// SDI panel on the invoice detail page (slot `invoice.detail.compliance`).
// Shows what the SDI is doing with this invoice — or why it is not an
// SDI document at all (art. 10-bis DL 119/2018) — with the manual-
// transport actions: download the FPR12, mark it exported, import the
// receipt, requeue after a scarto.
import { useSdiIt, fmtWhen, type SdiRecord } from '../../composables/useSdiIt'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

interface InvoiceCtx {
  invoice?: { id?: string, compliance_data?: Record<string, unknown> | null } | null
  clinic?: { country?: string | null } | null
}

const props = defineProps<{ ctx: InvoiceCtx }>()
const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { fetchLatestForInvoice, downloadXml, markExported, requeue, importReceipt } = useSdiIt()
const { fetchInvoice } = useInvoices()

const invoice = computed(() => props.ctx?.invoice ?? null)
const it = computed(() => (invoice.value?.compliance_data as Record<string, unknown> | null | undefined)?.IT as
  | { sdi?: string, reason?: string, error?: string }
  | undefined)

const record = ref<SdiRecord | null>(null)
const busy = ref(false)
const receiptOpen = ref(false)
const receiptXml = ref('')
const receiptFileName = ref('')

async function load() {
  if (!invoice.value?.id || !it.value || it.value.sdi === 'not_applicable') {
    record.value = null
    return
  }
  record.value = await fetchLatestForInvoice(invoice.value.id)
}
onMounted(load)
watch(() => invoice.value?.id, load)

const stateColor: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  pending: 'neutral',
  exported: 'info',
  delivered: 'success',
  undeliverable: 'warning',
  rejected: 'error',
  failed: 'error'
}

async function run(action: () => Promise<unknown>, okKey: string) {
  busy.value = true
  try {
    await action()
    toast.add({ title: t(okKey), color: 'success' })
    await load()
    if (invoice.value?.id) await fetchInvoice(invoice.value.id)
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sdi_it.panel.actionFailed')), color: 'error' })
  } finally {
    busy.value = false
  }
}

function onDownload() {
  if (record.value) run(() => downloadXml(record.value as SdiRecord), 'sdi_it.panel.downloaded')
}
function onExported() {
  if (record.value) run(() => markExported((record.value as SdiRecord).id), 'sdi_it.panel.markedExported')
}
function onRequeue() {
  if (record.value) run(() => requeue((record.value as SdiRecord).id), 'sdi_it.panel.requeued')
}
async function onReceiptFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  receiptFileName.value = file.name
  receiptXml.value = await file.text()
}
function onImportReceipt() {
  if (!receiptXml.value.trim()) return
  run(async () => {
    await importReceipt(receiptXml.value, receiptFileName.value || undefined)
    receiptOpen.value = false
    receiptXml.value = ''
    receiptFileName.value = ''
  }, 'sdi_it.panel.receiptImported')
}
</script>

<template>
  <UCard v-if="it">
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <span class="font-medium">{{ t('sdi_it.panel.title') }}</span>
        <UBadge
          v-if="record"
          :color="stateColor[record.state] ?? 'neutral'"
          variant="subtle"
        >
          {{ t(`sdi_it.state.${record.state}`) }}
        </UBadge>
      </div>
    </template>

    <!-- Patient invoice: analogue by law, reported through Sistema TS instead. -->
    <p
      v-if="it.sdi === 'not_applicable'"
      class="text-sm text-subtle"
    >
      {{ t('sdi_it.panel.notApplicable') }}
    </p>

    <p
      v-else-if="it.sdi === 'error'"
      class="text-sm text-red-500"
    >
      {{ t('sdi_it.panel.buildError') }}: {{ it.error }}
    </p>

    <div
      v-else-if="record"
      class="space-y-3 text-sm"
    >
      <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
        <dt class="text-subtle">
          {{ t('sdi_it.panel.file') }}
        </dt>
        <dd class="font-mono break-all">
          {{ record.file_name }}
        </dd>
        <dt class="text-subtle">
          {{ t('sdi_it.panel.recipient') }}
        </dt>
        <dd>{{ record.recipient_name }} · {{ record.recipient_tax_id }} · {{ record.codice_destinatario }}</dd>
        <dt class="text-subtle">
          {{ t('sdi_it.panel.transport') }}
        </dt>
        <dd>{{ record.transport ? t(`sdi_it.transport.${record.transport}`) : '—' }}<span v-if="record.sent_at"> · {{ fmtWhen(record.sent_at) }}</span></dd>
        <template v-if="record.receipt_type">
          <dt class="text-subtle">
            {{ t('sdi_it.panel.receipt') }}
          </dt>
          <dd>{{ record.receipt_type }} · {{ fmtWhen(record.receipt_at) }}<span v-if="record.sdi_identifier"> · IdSdI {{ record.sdi_identifier }}</span></dd>
        </template>
      </dl>
      <p
        v-if="record.error_message"
        class="text-xs text-red-500 break-words"
      >
        <span v-if="record.error_code">{{ record.error_code }}: </span>{{ record.error_message }}
      </p>
      <p
        v-if="record.state === 'undeliverable'"
        class="text-xs text-amber-600"
      >
        {{ t('sdi_it.panel.undeliverableHint') }}
      </p>
      <p
        v-if="record.state === 'rejected'"
        class="text-xs text-red-500"
      >
        {{ t('sdi_it.panel.rejectedHint') }}
      </p>

      <div class="flex flex-wrap gap-2">
        <UButton
          v-if="can(PERMISSIONS.sdiIt.recordsRead)"
          size="xs"
          variant="outline"
          icon="i-lucide-download"
          :loading="busy"
          @click="onDownload"
        >
          {{ t('sdi_it.panel.download') }}
        </UButton>
        <UButton
          v-if="record.state === 'pending' && can(PERMISSIONS.sdiIt.recordsManage)"
          size="xs"
          variant="soft"
          icon="i-lucide-upload"
          :loading="busy"
          @click="onExported"
        >
          {{ t('sdi_it.panel.markExported') }}
        </UButton>
        <UButton
          v-if="['exported', 'pending'].includes(record.state) && can(PERMISSIONS.sdiIt.recordsManage)"
          size="xs"
          variant="soft"
          icon="i-lucide-file-input"
          @click="receiptOpen = !receiptOpen"
        >
          {{ t('sdi_it.panel.importReceipt') }}
        </UButton>
        <UButton
          v-if="record.state === 'rejected' && can(PERMISSIONS.sdiIt.recordsManage)"
          size="xs"
          color="warning"
          variant="soft"
          icon="i-lucide-rotate-ccw"
          :loading="busy"
          @click="onRequeue"
        >
          {{ t('sdi_it.panel.requeue') }}
        </UButton>
      </div>

      <div
        v-if="receiptOpen"
        class="space-y-2 rounded-md border border-default p-3"
      >
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
          :rows="4"
          class="w-full font-mono text-xs"
          :placeholder="'<ns3:RicevutaConsegna …'"
        />
        <UButton
          size="xs"
          icon="i-lucide-check"
          :disabled="!receiptXml.trim()"
          :loading="busy"
          @click="onImportReceipt"
        >
          {{ t('sdi_it.panel.importReceipt') }}
        </UButton>
      </div>
    </div>

    <p
      v-else
      class="text-sm text-subtle"
    >
      {{ t('sdi_it.panel.noRecord') }}
    </p>
  </UCard>
</template>
