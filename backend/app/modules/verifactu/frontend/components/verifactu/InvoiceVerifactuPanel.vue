<script setup lang="ts">
// Inline panel rendered in the invoice detail page when the invoice
// has Verifactu compliance metadata (clinic.country=ES + verifactu
// installed and enabled).
const props = defineProps<{
  complianceData?: Record<string, unknown> | null
}>()

const { t } = useI18n()

const data = computed(() => {
  const cd = props.complianceData ?? {}
  return (cd.ES ?? null) as Record<string, string> | null
})

const stateColor = computed(() => {
  if (!data.value) return 'gray'
  if (data.value.state === 'accepted') return 'green'
  if (data.value.state === 'rejected') return 'red'
  if (data.value.state === 'accepted_with_errors') return 'amber'
  return 'gray'
})
</script>

<template>
  <UCard v-if="data">
    <template #header>
      <h3 class="font-semibold flex items-center gap-2">
        <UIcon name="i-lucide-shield-check" />
        {{ t('verifactu.panel.verifactuTitle') }}
      </h3>
    </template>
    <div class="text-sm space-y-2">
      <div class="flex items-center gap-2">
        <UBadge
          :color="stateColor"
          variant="subtle"
        >
          {{ t(`verifactu.recordState.${data.state ?? 'pending'}`) }}
        </UBadge>
        <UBadge variant="subtle">
          {{ data.tipo_factura }}
        </UBadge>
      </div>
      <div v-if="data.csv">
        <span class="text-gray-500">{{ t('verifactu.panel.csv') }}:</span>
        <code class="ml-2 font-mono break-all">{{ data.csv }}</code>
      </div>
      <div v-if="data.huella">
        <span class="text-gray-500">{{ t('verifactu.panel.huella') }}:</span>
        <code class="ml-2 font-mono text-xs break-all">{{ data.huella.slice(0, 24) }}…</code>
      </div>
      <div v-if="data.submitted_at">
        <span class="text-gray-500">{{ t('verifactu.panel.submittedAt') }}:</span>
        <span class="ml-2">{{ new Date(data.submitted_at).toLocaleString() }}</span>
      </div>
      <div v-else-if="data.state === 'pending'">
        <span class="text-gray-500">{{ t('verifactu.panel.stillPending') }}</span>
      </div>
      <UButton
        v-if="data.record_id"
        to="/settings/verifactu/records"
        variant="ghost"
        size="sm"
      >
        {{ t('verifactu.panel.viewRecord') }}
      </UButton>
    </div>
  </UCard>
</template>
