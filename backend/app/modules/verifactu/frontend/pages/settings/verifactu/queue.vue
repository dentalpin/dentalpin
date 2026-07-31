<script setup lang="ts">
import type { VerifactuQueueItem, VerifactuRecordAttempt } from '../../../composables/useVerifactu'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const { t } = useI18n()
const {
  listQueue,
  retryRecord,
  retryAllRejected,
  listRecordAttempts,
  processNow
} = useVerifactu()
const { can } = usePermissions()
const toast = useToast?.()

const tab = ref<'pending' | 'rejected' | 'failed_transient'>('pending')
const items = ref<VerifactuQueueItem[]>([])
const loading = ref(false)
const processing = ref(false)
const retryingAll = ref(false)
const retryingId = ref<string | null>(null)

const historyOpen = ref(false)
const historyAttempts = ref<VerifactuRecordAttempt[]>([])
const historyTitle = ref('')

async function refresh() {
  loading.value = true
  try {
    items.value = await listQueue(tab.value)
  } finally {
    loading.value = false
  }
}

async function retry(item: VerifactuQueueItem) {
  retryingId.value = item.id
  try {
    await retryRecord(item.id)
    toast?.add({
      title: t('verifactu.queue.regeneratedToast'),
      color: 'green'
    })
    await refresh()
  } catch (e: unknown) {
    toast?.add({
      title: errorMessage(e, 'Error'),
      color: 'red'
    })
  } finally {
    retryingId.value = null
  }
}

async function retryAll() {
  if (!confirm(t('verifactu.queue.retryAllConfirm'))) return
  retryingAll.value = true
  try {
    const r = await retryAllRejected()
    toast?.add({
      title: t('verifactu.queue.retryAllResult', {
        n: r.regenerated,
        failed: r.failed.length
      }),
      color: r.failed.length === 0 ? 'green' : 'amber'
    })
    await refresh()
  } finally {
    retryingAll.value = false
  }
}

async function openHistory(item: VerifactuQueueItem) {
  historyTitle.value = item.serie_numero
  historyAttempts.value = await listRecordAttempts(item.id)
  historyOpen.value = true
}

async function process() {
  processing.value = true
  try {
    const r = await processNow()
    toast?.add({ title: t('verifactu.queue.processed', { n: r.processed }), color: 'green' })
    await refresh()
  } finally {
    processing.value = false
  }
}

function isBusinessFailure(item: VerifactuQueueItem): boolean {
  if (item.state === 'rejected' || item.state === 'failed_validation') return true
  if (item.state === 'failed_transient') {
    const c = item.aeat_codigo_error
    return c !== null && (c === -2 || c >= 1000)
  }
  return false
}

function retryLabel(item: VerifactuQueueItem): string {
  return isBusinessFailure(item)
    ? t('verifactu.queue.regenerateAndRetry')
    : t('verifactu.queue.retry')
}

function retryTooltip(item: VerifactuQueueItem): string {
  return isBusinessFailure(item) ? t('verifactu.queue.regenerateTooltip') : ''
}

function ctaLabel(cta: string | null): string | null {
  if (!cta) return null
  return t(`verifactu.queue.ctas.${cta}`)
}

function ctaTarget(item: VerifactuQueueItem): string | null {
  switch (item.aeat_error_cta) {
    case 'edit_clinic':
      return '/settings/general/clinic'
    case 'edit_producer':
      return '/settings/verifactu/producer'
    case 'edit_billing_party':
      return `/invoices/${item.invoice_id}#fix-billing-party`
    case 'edit_lines':
      return `/invoices/${item.invoice_id}`
    default:
      return null
  }
}

watch(tab, refresh)
onMounted(refresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-4xl mx-auto space-y-4">
    <header class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <NuxtLink
          to="/settings/verifactu"
          class="text-sm text-gray-500"
        >← Verifactu</NuxtLink>
        <h1 class="text-2xl font-semibold mt-2">
          {{ t('verifactu.queue.title') }}
        </h1>
      </div>
      <div class="flex flex-wrap gap-2">
        <UButton
          v-if="tab === 'rejected' && can(PERMISSIONS.verifactu.queueManage) && items.length > 1"
          :loading="retryingAll"
          color="primary"
          variant="soft"
          icon="i-lucide-refresh-cw"
          @click="retryAll"
        >
          {{ t('verifactu.queue.retryAll') }}
        </UButton>
        <UButton
          v-if="can(PERMISSIONS.verifactu.queueManage)"
          :loading="processing"
          variant="soft"
          @click="process"
        >
          {{ t('verifactu.queue.processNow') }}
        </UButton>
      </div>
    </header>

    <div class="flex gap-2 border-b">
      <button
        v-for="t_ in (['pending', 'rejected', 'failed_transient'] as const)"
        :key="t_"
        class="px-3 py-2 text-sm border-b-2"
        :class="tab === t_ ? 'border-primary text-primary' : 'border-transparent text-gray-500'"
        @click="tab = t_"
      >
        {{ t(`verifactu.queue.tabs.${t_ === 'failed_transient' ? 'transient' : t_}`) }}
      </button>
    </div>

    <div
      v-if="loading"
      class="space-y-2"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-16 w-full"
      />
    </div>
    <p
      v-else-if="items.length === 0"
      class="text-sm text-gray-500"
    >
      {{ t('verifactu.queue.empty') }}
    </p>
    <ul
      v-else
      class="divide-y"
    >
      <li
        v-for="item in items"
        :key="item.id"
        class="py-3 flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between"
      >
        <div class="text-sm min-w-0 flex-1">
          <div class="font-medium">
            {{ item.serie_numero }} · {{ item.importe_total }}€
          </div>
          <div
            v-if="item.aeat_descripcion_error_es || item.aeat_descripcion_error"
            class="text-red-600 break-words mt-1"
          >
            <span v-if="item.aeat_codigo_error && item.aeat_codigo_error > 0">
              {{ t('verifactu.queue.errorCode') }} {{ item.aeat_codigo_error }}:
            </span>
            <span v-else-if="item.aeat_codigo_error === -1">
              {{ t('verifactu.queue.transportError') }}:
            </span>
            <span v-else-if="item.aeat_codigo_error === -2">
              {{ t('verifactu.queue.aeatFault') }}:
            </span>
            {{ item.aeat_descripcion_error_es || item.aeat_descripcion_error }}
            <details
              v-if="
                item.aeat_descripcion_error_es
                  && item.aeat_descripcion_error
                  && item.aeat_descripcion_error_es !== item.aeat_descripcion_error
              "
              class="mt-1 text-xs text-gray-500"
            >
              <summary class="cursor-pointer">
                {{ t('verifactu.queue.rawError') }}
              </summary>
              <pre class="whitespace-pre-wrap break-words mt-1">{{ item.aeat_descripcion_error }}</pre>
            </details>
          </div>
          <div class="text-gray-500 mt-1">
            {{ t('verifactu.queue.submissionAttempt', { n: item.submission_attempt }) }}
          </div>
        </div>
        <div class="flex flex-wrap gap-2">
          <UButton
            v-if="ctaTarget(item)"
            :to="ctaTarget(item) || undefined"
            variant="solid"
            color="primary"
            size="sm"
          >
            {{ ctaLabel(item.aeat_error_cta) }}
          </UButton>
          <UButton
            :to="`/invoices/${item.invoice_id}`"
            variant="soft"
            size="sm"
          >
            {{ t('verifactu.queue.viewInvoice') }}
          </UButton>
          <UButton
            v-if="can(PERMISSIONS.verifactu.recordsRead) && item.submission_attempt > 0"
            variant="ghost"
            size="sm"
            icon="i-lucide-history"
            @click="openHistory(item)"
          >
            {{ t('verifactu.queue.viewHistory') }}
          </UButton>
          <UButton
            v-if="
              can(PERMISSIONS.verifactu.queueManage)
                && ['rejected', 'failed_transient', 'failed_validation'].includes(item.state)
            "
            color="primary"
            size="sm"
            icon="i-lucide-refresh-cw"
            :loading="retryingId === item.id"
            :title="retryTooltip(item)"
            @click="retry(item)"
          >
            {{ retryLabel(item) }}
          </UButton>
        </div>
      </li>
    </ul>

    <UModal
      v-model:open="historyOpen"
      :title="`${t('verifactu.queue.history.title')} — ${historyTitle}`"
    >
      <template #body>
        <p
          v-if="historyAttempts.length === 0"
          class="text-sm text-gray-500"
        >
          {{ t('verifactu.queue.history.empty') }}
        </p>
        <ul
          v-else
          class="divide-y text-sm"
        >
          <li
            v-for="a in historyAttempts"
            :key="a.id"
            class="py-2"
          >
            <div class="font-medium">
              {{ t('verifactu.queue.history.attempt', { n: a.attempt_no }) }} · {{ a.state }}
            </div>
            <div class="text-xs text-gray-500 break-all">
              <span class="font-mono">{{ t('verifactu.queue.history.huella') }}:</span> {{ a.huella }}
            </div>
            <div
              v-if="a.aeat_codigo_error"
              class="text-xs text-red-600 mt-1"
            >
              {{ t('verifactu.queue.history.code') }} {{ a.aeat_codigo_error }} — {{ a.aeat_descripcion_error }}
            </div>
          </li>
        </ul>
      </template>
    </UModal>
  </div>
</template>
