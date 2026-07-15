<script setup lang="ts">
/**
 * Soft warning shown when the user is viewing a closed snapshot in
 * read-only mode. Mirrors the odontogram's "viendo histórico"
 * pattern — non-blocking, single CTA back to live state.
 */

defineProps<{
  date: string
}>()

const emit = defineEmits<{
  returnToCurrent: []
}>()

const { t, locale } = useI18n()

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'long',
      year: 'numeric'
    })
  } catch {
    return iso
  }
}
</script>

<template>
  <div
    class="perio-history-banner flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-200"
  >
    <div class="flex items-center gap-2">
      <UIcon name="i-lucide-history" />
      <span>{{ t('periodontogram.history.viewingSession', { date: formatDate(date) }) }}</span>
    </div>
    <UButton variant="outline" size="xs" @click="emit('returnToCurrent')">
      {{ t('periodontogram.history.returnToCurrent') }}
    </UButton>
  </div>
</template>
