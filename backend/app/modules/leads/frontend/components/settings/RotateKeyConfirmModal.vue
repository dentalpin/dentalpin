<script setup lang="ts">
interface Props {
  open: boolean
  loading?: boolean
  error?: string | null
}

defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': []
}>()
const { t } = useI18n()

function closeModal(loading?: boolean) {
  if (!loading) {
    emit('update:open', false)
  }
}
</script>

<template>
  <UModal
    :open="open"
    :dismissible="!loading"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-key-round"
              class="w-5 h-5 text-danger-accent"
            />
            <h3 class="font-semibold text-default">
              {{ t('leads.settings.confirmRotate.title') }}
            </h3>
          </div>
        </template>

        <div class="space-y-3">
          <p class="text-muted">
            {{ t('leads.settings.confirmRotate.message') }}
          </p>

          <div
            v-if="error"
            class="rounded-md bg-[var(--color-danger-soft)] p-3 text-sm text-danger-accent"
          >
            {{ error }}
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-6">
          <UButton
            variant="ghost"
            :disabled="loading"
            @click="closeModal(loading)"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            color="error"
            :loading="loading"
            @click="emit('confirm')"
          >
            {{ t('leads.settings.rotate') }}
          </UButton>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
