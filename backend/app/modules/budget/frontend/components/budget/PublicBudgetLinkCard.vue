<script setup lang="ts">
/**
 * PublicBudgetLinkCard — surfaces the patient-facing URL for a sent
 * budget (ADR 0006) so reception can copy it into WhatsApp / SMS /
 * email signature. Adds a one-tap WhatsApp deep link when the
 * patient phone is on file.
 */

const props = defineProps<{
  token: string
  status: string
  patientPhone?: string | null
  patientFirstName?: string | null
  budgetNumber?: string | null
}>()

const { t } = useI18n()
const toast = useToast()

const url = computed(() => {
  if (typeof window === 'undefined') return `/p/budget/${props.token}`
  return `${window.location.origin}/p/budget/${props.token}`
})

const whatsappUrl = computed(() => {
  if (!props.patientPhone) return null
  const digits = props.patientPhone.replace(/\D/g, '')
  if (!digits) return null
  const greeting = props.patientFirstName
    ? t('budget.publicLink.whatsappGreeting', { name: props.patientFirstName })
    : t('budget.publicLink.whatsappGreetingFallback')
  const text = `${greeting} ${url.value}`
  return `https://wa.me/${digits}?text=${encodeURIComponent(text)}`
})

const copyState = ref<'idle' | 'copied'>('idle')
let copyResetTimer: ReturnType<typeof setTimeout> | null = null

async function copyUrl() {
  try {
    await navigator.clipboard.writeText(url.value)
  } catch {
    // Fallback when clipboard API is unavailable (older browsers / iframes)
    const ta = document.createElement('textarea')
    ta.value = url.value
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
    } finally {
      document.body.removeChild(ta)
    }
  }
  copyState.value = 'copied'
  toast.add({
    title: t('budget.publicLink.copied'),
    color: 'success',
    icon: 'i-lucide-check-circle-2'
  })
  if (copyResetTimer) clearTimeout(copyResetTimer)
  copyResetTimer = setTimeout(() => {
    copyState.value = 'idle'
  }, 2000)
}

const statusLabel = computed(() => {
  switch (props.status) {
    case 'sent':
      return t('budget.publicLink.statusSent')
    case 'accepted':
      return t('budget.publicLink.statusAccepted')
    case 'rejected':
      return t('budget.publicLink.statusRejected')
    case 'expired':
      return t('budget.publicLink.statusExpired')
    default:
      return ''
  }
})
</script>

<template>
  <UCard class="public-link-card">
    <div class="flex items-start gap-3">
      <div class="icon-wrap">
        <UIcon
          name="i-lucide-link-2"
          class="w-5 h-5"
        />
      </div>
      <div class="min-w-0 flex-1 space-y-3">
        <div class="flex items-center gap-2 flex-wrap">
          <h2 class="text-base font-semibold">
            {{ t('budget.publicLink.title') }}
          </h2>
          <UBadge
            color="neutral"
            variant="soft"
            size="xs"
          >
            {{ statusLabel }}
          </UBadge>
        </div>
        <p class="text-sm text-[var(--ui-text-muted)]">
          {{ t('budget.publicLink.help') }}
        </p>

        <div class="url-box">
          <span
            class="url-text"
            :title="url"
          >{{ url }}</span>
          <UButton
            :color="copyState === 'copied' ? 'success' : 'primary'"
            variant="solid"
            size="sm"
            :icon="copyState === 'copied' ? 'i-lucide-check' : 'i-lucide-copy'"
            @click="copyUrl"
          >
            {{ copyState === 'copied' ? t('budget.publicLink.copied') : t('budget.publicLink.copy') }}
          </UButton>
        </div>

        <div class="flex flex-wrap gap-2">
          <UButton
            v-if="whatsappUrl"
            color="success"
            variant="soft"
            icon="i-lucide-message-circle"
            size="sm"
            :to="whatsappUrl"
            target="_blank"
            rel="noopener"
          >
            {{ t('budget.publicLink.whatsapp') }}
          </UButton>
          <UButton
            v-else
            color="neutral"
            variant="soft"
            icon="i-lucide-message-circle"
            size="sm"
            disabled
            :title="t('budget.publicLink.whatsappNoPhone')"
          >
            {{ t('budget.publicLink.whatsapp') }}
          </UButton>
          <UButton
            color="neutral"
            variant="soft"
            icon="i-lucide-external-link"
            size="sm"
            :to="url"
            target="_blank"
            rel="noopener"
          >
            {{ t('budget.publicLink.preview') }}
          </UButton>
        </div>
      </div>
    </div>
  </UCard>
</template>

<style scoped>
.public-link-card {
  border-color: color-mix(in srgb, var(--ui-primary) 30%, var(--ui-border) 70%);
  background: color-mix(in srgb, var(--ui-primary) 5%, var(--ui-bg-elevated) 95%);
}

.icon-wrap {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--ui-primary) 16%, transparent);
  color: var(--ui-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.url-box {
  display: flex;
  align-items: stretch;
  gap: 8px;
  background: var(--ui-bg);
  border: 1px solid var(--ui-border);
  border-radius: 8px;
  padding: 6px 6px 6px 12px;
}

.url-text {
  flex: 1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  color: var(--ui-text);
  align-self: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
</style>
