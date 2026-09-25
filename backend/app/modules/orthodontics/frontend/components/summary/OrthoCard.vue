<script setup lang="ts">
/**
 * Patient summary mini-card: active orthodontic case at a glance.
 * Rendered only when a case exists (L10: failures must render).
 */
import type { OrthoCase } from '../../composables/useOrthodontics'

const props = defineProps<{ patientId: string }>()

const { t } = useI18n()
const { listCases } = useOrthodontics()

const active = ref<OrthoCase | null>(null)

onMounted(async () => {
  try {
    const rows = await listCases({ patient_id: props.patientId })
    active.value = rows.find(c => c.status === 'active' || c.status === 'paused') || null
  } catch {
    active.value = null
  }
})
</script>

<template>
  <UCard v-if="active">
    <template #header>
      <span class="font-semibold">{{ t('orthodontics.card.title') }}</span>
    </template>
    <div class="text-sm">
      {{ t(`orthodontics.appliance.${active.appliance_type}`) }} ·
      {{ t(`orthodontics.status.${active.status}`) }}
      <span v-if="active.estimated_months">
        · {{ t('orthodontics.inbox.monthOf', { x: active.control_count, n: active.estimated_months }) }}
      </span>
    </div>
    <template #footer>
      <UButton
        size="sm"
        variant="soft"
        :to="`/orthodontics?case_id=${active.id}`"
      >
        {{ t('orthodontics.card.view') }}
      </UButton>
    </template>
  </UCard>
</template>
