<script setup lang="ts">
// Reusable AEAT badge: same component for the invoice list row and
// the invoice detail header. Rendered via slots
// `invoice.list.row.meta` and `invoice.detail.header.meta`.

import type { ComplianceData } from '../../composables/useComplianceBadge'

interface InvoiceCtx {
  invoice?: {
    compliance_data?: ComplianceData | null
  } | null
  clinic?: { country?: string | null } | null
}

const props = defineProps<{ ctx: InvoiceCtx }>()

const compliance = computed(() => props.ctx?.invoice?.compliance_data ?? null)
const badge = useComplianceBadge(compliance)
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
      {{ badge.shortLabel }}
    </UBadge>
  </UTooltip>
</template>
