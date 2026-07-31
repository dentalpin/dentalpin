<script setup lang="ts">
/**
 * Slot entry into ``reports.categories``.
 *
 * Renders the payments report card on ``/reports``. The visual shape
 * matches the native reports module's category cards — no shared
 * component because that would create an inter-layer import. Tailwind
 * primitives keep it consistent.
 */

const { t } = useI18n()
</script>

<template>
  <UCard
    class="transition-all hover:shadow-lg cursor-pointer hover:scale-[1.02]"
    @click="navigateTo('/reports/payments')"
  >
    <div class="flex flex-col items-center text-center space-y-4 py-4">
      <div class="p-4 rounded-full bg-surface-muted">
        <UIcon
          name="i-lucide-wallet"
          class="h-8 w-8 text-amber-600"
        />
      </div>

      <div>
        <h3 class="text-h1 text-default flex items-center justify-center gap-2">
          {{ t('payments.reports.title') }}
        </h3>
        <p class="text-caption text-subtle mt-1">
          {{ t('payments.reports.cardDescription') }}
        </p>
      </div>

      <UButton
        variant="soft"
        trailing-icon="i-lucide-arrow-right"
        @click.stop="navigateTo('/reports/payments')"
      >
        {{ t('reports.viewReports') }}
      </UButton>
    </div>
  </UCard>
</template>
