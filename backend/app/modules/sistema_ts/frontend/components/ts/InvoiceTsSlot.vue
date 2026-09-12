<script setup lang="ts">
// Invoice page panel: what the Sistema TS did with this patient invoice
// (inserimento / rimborso / cancellazione / variazione rows). Hidden for
// B2B invoices (the SDI's) and until the first document exists.
import { useSistemaTs, fmtWhen, type TsDocument } from '../../composables/useSistemaTs'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

interface InvoiceCtx {
  invoice?: { id?: string, status?: string, billing_tax_id?: string | null } | null
}

const props = defineProps<{ ctx: InvoiceCtx }>()
const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const { fetchForInvoice, retry } = useSistemaTs()

const docs = ref<TsDocument[]>([])
const busy = ref(false)

const isBusiness = computed(() => {
  const id = (props.ctx.invoice?.billing_tax_id ?? '').replace(/\W/g, '').replace(/^IT/i, '')
  return id.length === 11 && /^\d+$/.test(id)
})

async function load() {
  if (!props.ctx.invoice?.id || isBusiness.value) {
    docs.value = []
    return
  }
  try {
    docs.value = await fetchForInvoice(props.ctx.invoice.id)
  } catch {
    docs.value = []
  }
}
onMounted(load)
watch(() => props.ctx.invoice?.id, load)

const stateColor: Record<string, 'success' | 'warning' | 'error' | 'neutral' | 'info'> = {
  pending: 'neutral',
  sending: 'info',
  accepted: 'success',
  accepted_with_warnings: 'warning',
  rejected: 'error',
  failed: 'error'
}

async function onRetry(d: TsDocument) {
  busy.value = true
  try {
    await retry(d.id)
    toast.add({ title: t('sistema_ts.documents.requeued'), color: 'success' })
    await load()
  } catch (e) {
    toast.add({ title: t('common.error'), description: errorMessage(e, t('sistema_ts.documents.actionFailed')), color: 'error' })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <UCard v-if="!isBusiness && (docs.length || ctx.invoice?.status === 'paid')">
    <template #header>
      <span class="font-medium">{{ t('sistema_ts.panel.title') }}</span>
    </template>
    <p
      v-if="!docs.length"
      class="text-sm text-subtle"
    >
      {{ t('sistema_ts.panel.waiting') }}
    </p>
    <ul
      v-else
      class="space-y-2 text-sm"
    >
      <li
        v-for="d in docs"
        :key="d.id"
        class="flex flex-wrap items-center gap-2"
      >
        <span class="font-medium">{{ t(`sistema_ts.operation.${d.operation}`) }}</span>
        <UBadge
          :color="stateColor[d.state] ?? 'neutral'"
          variant="subtle"
        >
          {{ t(`sistema_ts.state.${d.state}`) }}
        </UBadge>
        <span
          v-if="d.protocollo"
          class="font-mono text-xs"
        >{{ t('sistema_ts.documents.protocollo') }} {{ d.protocollo }}</span>
        <span class="text-xs text-subtle">{{ fmtWhen(d.finished_at ?? d.sent_at ?? d.created_at) }}</span>
        <span
          v-if="d.flag_opposizione"
          class="text-xs text-amber-600"
        >{{ t('sistema_ts.opposition.opposed') }}</span>
        <span
          v-if="d.error_message"
          class="text-xs text-red-500 basis-full"
        >{{ d.error_message }}</span>
        <UButton
          v-if="['rejected', 'failed'].includes(d.state) && can(PERMISSIONS.sistemaTs.documentsManage)"
          size="xs"
          variant="soft"
          icon="i-lucide-rotate-ccw"
          :loading="busy"
          @click="onRetry(d)"
        >
          {{ t('sistema_ts.documents.retry') }}
        </UButton>
      </li>
    </ul>
  </UCard>
</template>
