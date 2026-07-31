<script setup lang="ts">
import type { BudgetSignatureMeta } from '../../composables/useBudgets'

interface Props {
  budgetId: string
  budgetStatus: string
  locale?: string
}

const props = withDefaults(defineProps<Props>(), { locale: 'es' })

const { t, locale: i18nLocale } = useI18n()
const toast = useToast()
const { fetchSignature, downloadSignedPDF } = useBudgets()

const signature = ref<BudgetSignatureMeta | null>(null)
const isLoading = ref(false)
const isDownloading = ref(false)

const visible = computed(() => ['accepted', 'completed'].includes(props.budgetStatus))

async function load() {
  if (!visible.value) return
  isLoading.value = true
  try {
    signature.value = await fetchSignature(props.budgetId)
  } finally {
    isLoading.value = false
  }
}

watch(() => [props.budgetId, props.budgetStatus], load, { immediate: true })

const methodLabel = computed(() => {
  if (!signature.value) return ''
  const m = signature.value.signature_method
  if (m === 'drawn') return t('budget.signature.method.drawn')
  if (m === 'click_accept') return t('budget.signature.method.clickAccept')
  if (m === 'external_provider') return t('budget.signature.method.external')
  return m
})

const pngDataUrl = computed(() => {
  // Metadata endpoint omits the PNG. We only show the visual when the
  // user downloads — the card focuses on audit data.
  return null
})

async function onDownload() {
  isDownloading.value = true
  try {
    await downloadSignedPDF(props.budgetId, props.locale || i18nLocale.value)
  } catch (e) {
    console.error(e)
    toast.add({
      title: t('common.error'),
      description: t('budget.signature.downloadError'),
      color: 'error'
    })
  } finally {
    isDownloading.value = false
  }
}

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(i18nLocale.value === 'es' ? 'es-ES' : 'en-US', {
    dateStyle: 'medium',
    timeStyle: 'short'
  })
}

function shortHash(hash: string | null): string {
  if (!hash) return ''
  return `${hash.slice(0, 8)}…${hash.slice(-4)}`
}
</script>

<template>
  <UCard v-if="visible">
    <template #header>
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-pen-tool"
          class="text-primary-accent"
        />
        <h3 class="text-h2 text-default">
          {{ t('budget.signature.title') }}
        </h3>
      </div>
    </template>

    <div
      v-if="isLoading"
      class="flex items-center gap-2 text-sm text-subtle"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="animate-spin"
      />
      {{ t('common.loading') }}
    </div>

    <div
      v-else-if="!signature"
      class="text-sm text-subtle"
    >
      {{ t('budget.signature.notSigned') }}
    </div>

    <div
      v-else
      class="space-y-3 text-sm"
    >
      <div
        v-if="pngDataUrl"
        class="rounded-md border border-default p-2 bg-elevated"
      >
        <img
          :src="pngDataUrl"
          alt="signature"
          class="max-h-24 mx-auto"
        >
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <span class="text-subtle">{{ t('budget.signature.signedBy') }}</span>
          <p class="font-medium">
            {{ signature.signed_by_name }}
          </p>
        </div>
        <div>
          <span class="text-subtle">{{ t('budget.signature.signedAt') }}</span>
          <p class="font-medium">
            {{ formatDateTime(signature.signed_at) }}
          </p>
        </div>
        <div>
          <span class="text-subtle">{{ t('budget.signature.methodLabel') }}</span>
          <p class="font-medium">
            {{ methodLabel }}
          </p>
        </div>
        <div>
          <span class="text-subtle">{{ t('budget.signature.relationshipLabel') }}</span>
          <p class="font-medium">
            {{ t(`budget.signature.${signature.relationship_to_patient}`) }}
          </p>
        </div>
        <div
          v-if="signature.document_hash"
          class="sm:col-span-2"
        >
          <span class="text-subtle">{{ t('budget.signature.documentHash') }}</span>
          <p class="font-mono text-xs break-all">
            {{ signature.document_hash }}
          </p>
        </div>
      </div>

      <UButton
        block
        icon="i-lucide-download"
        :loading="isDownloading"
        @click="onDownload"
      >
        {{ t('budget.signature.downloadSignedPdf') }}
      </UButton>

      <p class="text-xs text-subtle">
        {{ t('budget.signature.hashHint', { short: shortHash(signature.document_hash) }) }}
      </p>
    </div>
  </UCard>
</template>
