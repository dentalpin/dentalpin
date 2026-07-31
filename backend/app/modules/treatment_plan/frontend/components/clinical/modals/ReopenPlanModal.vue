<script setup lang="ts">
/**
 * ReopenPlanModal — pending → draft, cancels linked budget.
 * Warns the user that the current quote will be cancelled.
 */

defineProps<{
  open: boolean
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
            {{ t('treatmentPlans.modals.reopen.title') }}
          </h2>
        </template>

        <p class="text-sm">
          {{ t('treatmentPlans.modals.reopen.description') }}
        </p>

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
              color="warning"
              :loading="loading"
              @click="emit('confirm')"
            >
              {{ t('treatmentPlans.modals.reopen.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
