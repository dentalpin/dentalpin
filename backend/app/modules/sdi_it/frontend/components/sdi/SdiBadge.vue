<script setup lang="ts">
// Compact SDI chip for the invoice list row and the invoice detail
// header. Reads the IT block of ``compliance_data``; renders nothing
// for invoices the SDI does not concern (patients).

interface InvoiceCtx {
  invoice?: { compliance_data?: Record<string, unknown> | null } | null
}

const props = defineProps<{ ctx: InvoiceCtx }>()
const { t } = useI18n()

const it = computed(() => (props.ctx?.invoice?.compliance_data as Record<string, unknown> | null | undefined)?.IT as
  | { sdi?: string, state?: string, reason?: string, error?: string }
  | undefined)

const badge = computed(() => {
  const block = it.value
  if (!block || block.sdi === 'not_applicable') return null
  if (block.sdi === 'error') {
    return { color: 'error' as const, icon: 'i-lucide-x', tooltip: block.error ?? t('sdi_it.badge.error') }
  }
  const state = block.state ?? 'pending'
  const color = state === 'delivered' ? 'success' : state === 'rejected' || state === 'failed' ? 'error' : state === 'undeliverable' ? 'warning' : 'info'
  return { color: color as 'success' | 'error' | 'warning' | 'info', icon: 'i-lucide-file-check-2', tooltip: t(`sdi_it.state.${state}`) }
})
</script>

<template>
  <UTooltip
    v-if="badge"
    :text="badge.tooltip"
  >
    <UBadge
      :color="badge.color"
      variant="subtle"
      size="xs"
      :icon="badge.icon"
      class="cursor-help"
    >
      {{ t('sdi_it.badge.short') }}
    </UBadge>
  </UTooltip>
</template>
