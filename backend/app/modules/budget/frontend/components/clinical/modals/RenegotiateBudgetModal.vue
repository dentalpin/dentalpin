<script setup lang="ts">
/**
 * RenegotiateBudgetModal — cancels the sent budget and reopens the
 * linked plan so reception can edit treatments and reissue.
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
            {{ t('budget.modals.renegotiate.title') }}
          </h2>
        </template>

        <p class="text-sm">
          {{ t('budget.modals.renegotiate.description') }}
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
              {{ t('budget.modals.renegotiate.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
