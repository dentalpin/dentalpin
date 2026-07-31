<script setup lang="ts">
const { t } = useI18n()
const { settings, loading, saving, fetch, update } = useBudgetSettings()

const authDisabled = ref(false)

watch(settings, (s) => {
  if (s) authDisabled.value = s.budget_public_auth_disabled
})

onMounted(fetch)

async function save() {
  await update({ budget_public_auth_disabled: authDisabled.value })
}
</script>

<template>
  <UCard v-if="!loading">
    <div class="space-y-4">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="font-medium">
            {{ t('budget.settings.publicLink.authDisabled') }}
          </p>
          <p class="text-xs text-[var(--ui-text-muted)] mt-1 max-w-xl">
            {{ t('budget.settings.publicLink.authDisabledHelp') }}
          </p>
        </div>
        <USwitch v-model="authDisabled" />
      </div>
      <UAlert
        v-if="authDisabled"
        color="warning"
        variant="soft"
        icon="i-lucide-shield-alert"
        :description="t('budget.settings.publicLink.authDisabledHelp')"
      />
    </div>
    <template #footer>
      <div class="flex justify-end">
        <UButton
          color="primary"
          :loading="saving"
          @click="save"
        >
          {{ t('budget.settings.publicLink.save') }}
        </UButton>
      </div>
    </template>
  </UCard>
</template>
