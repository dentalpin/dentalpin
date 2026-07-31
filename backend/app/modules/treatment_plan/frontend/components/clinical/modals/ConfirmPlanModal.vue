<script setup lang="ts">
/**
 * ConfirmPlanModal — doctor closes the plan clinically (draft → pending).
 * Triggers an automatic draft budget creation server-side.
 */

defineProps<{
  open: boolean
  planNumber?: string | null
  itemCount?: number
  totalEstimated?: number | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': []
  'cancel': []
}>()

const { t } = useI18n()
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('treatmentPlans.modals.confirm.title') }}
          </h2>
        </template>

        <div class="space-y-4 text-sm">
          <p>{{ t('treatmentPlans.modals.confirm.description') }}</p>
          <div
            v-if="planNumber || itemCount || totalEstimated"
            class="rounded-md bg-[var(--ui-bg-elevated)] p-3 space-y-1"
          >
            <div v-if="planNumber">
              <strong>{{ planNumber }}</strong>
            </div>
            <div v-if="itemCount !== undefined">
              {{ t('treatmentPlans.itemCount', { count: itemCount }, itemCount) }}
            </div>
            <div v-if="totalEstimated !== null && totalEstimated !== undefined">
              {{ totalEstimated.toFixed(2) }} €
            </div>
          </div>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="loading"
              @click="emit('cancel')"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="loading"
              @click="emit('confirm')"
            >
              {{ t('treatmentPlans.modals.confirm.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
