<script setup lang="ts">
/**
 * Empty state for the periodontogram sub-tab.
 *
 * Rendered when the patient has no closed snapshots and no active
 * draft. Single CTA opens a fresh draft via the parent.
 */

defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  start: []
}>()

const { t } = useI18n()
</script>

<template>
  <UCard class="perio-empty-state">
    <div class="flex flex-col items-center gap-3 py-10 text-center">
      <div
        class="flex h-14 w-14 items-center justify-center rounded-full bg-primary-50 text-primary-600 dark:bg-primary-950/40 dark:text-primary-300"
      >
        <UIcon
          name="i-lucide-activity"
          class="text-2xl"
        />
      </div>
      <h3 class="text-lg font-semibold text-default">
        {{ t('periodontogram.empty.title') }}
      </h3>
      <p class="max-w-md text-sm text-muted">
        {{ t('periodontogram.empty.description') }}
      </p>
      <UButton
        :loading="loading"
        icon="i-lucide-plus"
        size="md"
        class="mt-2"
        @click="emit('start')"
      >
        {{ t('periodontogram.empty.cta') }}
      </UButton>
    </div>
  </UCard>
</template>
