<script setup lang="ts">
const { t } = useI18n()
const { settings, loading, saving, fetch, update } = useBudgetSettings()

const remindersEnabled = ref(false)

watch(settings, (s) => {
  if (s) remindersEnabled.value = s.budget_reminders_enabled
})

onMounted(fetch)

async function save() {
  await update({ budget_reminders_enabled: remindersEnabled.value })
}
</script>

<template>
  <UCard v-if="!loading">
    <div class="space-y-4">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="font-medium">
            {{ t('budget.settings.reminders.enabled') }}
          </p>
          <p class="text-xs text-[var(--ui-text-muted)] mt-1 max-w-xl">
            {{ t('budget.settings.reminders.enabledHelp') }}
          </p>
        </div>
        <USwitch v-model="remindersEnabled" />
      </div>
    </div>
    <template #footer>
      <div class="flex justify-end">
        <UButton
          color="primary"
          :loading="saving"
          @click="save"
        >
          {{ t('budget.settings.reminders.save') }}
        </UButton>
      </div>
    </template>
  </UCard>
</template>
