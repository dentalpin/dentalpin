<script setup lang="ts">
// Slot adapter mounted at <ModuleSlot name="invoice.detail.compliance">.
// Renders the rejection banner + edit-billing-party modal in addition
// to the compliance summary panel. Billing has no compile-time
// dependency on verifactu; this file lives in the verifactu module and
// is loaded only when the clinic country is ES.
import InvoiceVerifactuPanel from './InvoiceVerifactuPanel.vue'
import { errorMessage, errorStatus } from '~~/app/utils/error'

interface InvoiceCtx {
  invoice?: {
    id?: string
    billing_name?: string | null
    billing_tax_id?: string | null
    billing_address?: Record<string, unknown> | null
    compliance_data?: Record<string, unknown> | null
    pdf_stale?: boolean
    updated_at?: string | null
  } | null
  clinic?: { country?: string | null } | null
}

const props = defineProps<{ ctx: InvoiceCtx }>()
const { t } = useI18n()
const router = useRouter()
const toast = useToast?.()
const { retryRecord, checkNif, getLatestRecordForInvoice } = useVerifactu()
const { updateBillingParty, fetchInvoice } = useInvoices()

const invoice = computed(() => props.ctx?.invoice ?? null)
const complianceData = computed(() => invoice.value?.compliance_data ?? null)

const es = computed(
  () =>
    ((complianceData.value as Record<string, unknown> | null)?.ES ?? null) as
    | Record<string, string | number | null>
    | null
)

// Live record state from the backend — overrides compliance_data when
// available. Older invoices issued before submission_queue mirrored
// rejected state into compliance_data still show "pending" there even
// though the record is actually rejected; this fetch reconciles them.
const liveRecord = ref<{
  state: string
  aeat_codigo_error: number | null
  aeat_descripcion_error: string | null
  id: string
} | null>(null)

async function fetchLiveRecord() {
  if (!invoice.value?.id) return
  try {
    const r = await getLatestRecordForInvoice(invoice.value.id)
    if (r) {
      liveRecord.value = {
        state: r.state,
        aeat_codigo_error: r.aeat_codigo_error,
        aeat_descripcion_error: r.aeat_descripcion_error,
        id: r.id
      }
    }
  } catch {
    liveRecord.value = null
  }
}

onMounted(fetchLiveRecord)
watch(() => invoice.value?.id, fetchLiveRecord)

const state = computed(
  () => liveRecord.value?.state ?? (es.value?.state as string | undefined) ?? null
)
const errorMessage = computed(
  () =>
    liveRecord.value?.aeat_descripcion_error
    ?? (es.value?.error_message as string | undefined)
    ?? null
)

const errorCode = computed(() => liveRecord.value?.aeat_codigo_error ?? null)

// Treat failed_transient as a logical rejection when AEAT pushed back
// at the data layer (-2 SOAP fault wrapping a validation error, or
// any 4xxx code). Plain transport failures (-1) keep their
// auto-retry status and don't surface a banner.
const isRejected = computed(() => {
  if (state.value === 'rejected' || state.value === 'failed_validation') return true
  if (state.value === 'failed_transient') {
    const c = errorCode.value
    return c !== null && (c === -2 || c >= 1000)
  }
  return false
})
const isAccepted = computed(() => state.value === 'accepted' || state.value === 'accepted_with_errors')

const editOpen = ref(false)
const editName = ref('')
const editTaxId = ref('')
const editAddress = ref<Record<string, unknown> | null>(null)
const nifWarning = ref<string | null>(null)
const saving = ref(false)
const regenerating = ref(false)

function openEdit() {
  editName.value = invoice.value?.billing_name ?? ''
  editTaxId.value = invoice.value?.billing_tax_id ?? ''
  editAddress.value = invoice.value?.billing_address ?? null
  nifWarning.value = null
  editOpen.value = true
}

async function onNifBlur() {
  if (!editTaxId.value) {
    nifWarning.value = null
    return
  }
  try {
    const r = await checkNif(editTaxId.value)
    nifWarning.value = r.warning
  } catch {
    nifWarning.value = null
  }
}

async function save() {
  if (!invoice.value?.id) return
  saving.value = true
  try {
    await updateBillingParty(invoice.value.id, {
      billing_name: editName.value || null,
      billing_tax_id: editTaxId.value || null,
      billing_address: editAddress.value,
      expected_updated_at: invoice.value.updated_at ?? null
    })
    toast?.add({ title: t('verifactu.billingParty.saved'), color: 'green' })
    editOpen.value = false
    await fetchInvoice(invoice.value.id)
    await fetchLiveRecord()
  } catch (e: unknown) {
    const msg = errorStatus(e) === 409
      ? t('verifactu.billingParty.concurrentEdit')
      : errorMessage(e, t('verifactu.billingParty.saveFailed'))
    toast?.add({ title: msg, color: 'red' })
  } finally {
    saving.value = false
  }
}

async function regenerate() {
  const recordId
    = liveRecord.value?.id ?? (es.value?.record_id as string | undefined)
  if (!recordId) return
  regenerating.value = true
  try {
    await retryRecord(recordId)
    toast?.add({ title: t('verifactu.queue.regeneratedToast'), color: 'green' })
    if (invoice.value?.id) await fetchInvoice(invoice.value.id)
    await fetchLiveRecord()
  } catch (e: unknown) {
    toast?.add({ title: errorMessage(e, t('verifactu.billingParty.saveFailed')), color: 'red' })
  } finally {
    regenerating.value = false
  }
}

function goToClinic() {
  router.push('/settings/general/clinic')
}
</script>

<template>
  <div class="space-y-3">
    <UAlert
      v-if="isRejected"
      color="red"
      variant="soft"
      icon="i-lucide-alert-triangle"
      :title="t('verifactu.invoiceBanner.rejectedTitle')"
    >
      <template #description>
        <p class="mb-2">
          {{ errorMessage || t('verifactu.invoiceBanner.rejectedBody') }}
        </p>
        <div class="flex flex-wrap gap-2">
          <UButton
            color="primary"
            size="sm"
            icon="i-lucide-user-pen"
            @click="openEdit"
          >
            {{ t('verifactu.queue.ctas.edit_billing_party') }}
          </UButton>
          <UButton
            variant="soft"
            size="sm"
            icon="i-lucide-building-2"
            @click="goToClinic"
          >
            {{ t('verifactu.queue.ctas.edit_clinic') }}
          </UButton>
          <UButton
            variant="ghost"
            size="sm"
            icon="i-lucide-refresh-cw"
            :loading="regenerating"
            @click="regenerate"
          >
            {{ t('verifactu.queue.regenerateAndRetry') }}
          </UButton>
        </div>
      </template>
    </UAlert>

    <UAlert
      v-if="isAccepted && invoice?.pdf_stale"
      color="amber"
      variant="soft"
      icon="i-lucide-file-warning"
      :title="t('verifactu.invoiceBanner.pdfStaleTitle')"
    >
      <template #description>
        <p class="mb-2">
          {{ t('verifactu.invoiceBanner.pdfStaleBody') }}
        </p>
        <UButton
          :to="`/api/v1/billing/invoices/${invoice.id}/pdf`"
          target="_blank"
          size="sm"
        >
          {{ t('verifactu.invoiceBanner.downloadAgain') }}
        </UButton>
      </template>
    </UAlert>

    <InvoiceVerifactuPanel :compliance-data="complianceData" />

    <UModal
      v-model:open="editOpen"
      :title="t('verifactu.billingParty.modalTitle')"
    >
      <template #body>
        <p class="text-sm text-gray-600 mb-3">
          {{ t('verifactu.billingParty.intro') }}
        </p>
        <div class="space-y-3">
          <UFormField :label="t('verifactu.billingParty.fields.name')">
            <UInput
              v-model="editName"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('verifactu.billingParty.fields.taxId')"
            :hint="nifWarning || undefined"
            :color="nifWarning ? 'warning' : undefined"
          >
            <UInput
              v-model="editTaxId"
              class="w-full"
              @blur="onNifBlur"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2 w-full">
          <UButton
            variant="ghost"
            @click="editOpen = false"
          >
            {{ t('actions.cancel') }}
          </UButton>
          <UButton
            color="primary"
            :loading="saving"
            @click="save"
          >
            {{ t('verifactu.billingParty.save') }}
          </UButton>
        </div>
      </template>
    </UModal>
  </div>
</template>
