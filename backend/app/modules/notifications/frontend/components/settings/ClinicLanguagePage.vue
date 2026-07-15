<script setup lang="ts">
const { t } = useI18n()
const { settings, loading, saving, fetch, update } = useCommunicationsSettings()

const language = ref<'es' | 'en' | 'fr'>('es')

watch(settings, (s) => {
  if (s) language.value = (s.language === 'en' || s.language === 'fr' ? s.language : 'es')
})

onMounted(fetch)

const options = [
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
]

async function save() {
  await update({ language: language.value })
}
</script>

<template>
  <UCard v-if="!loading">
    <div class="space-y-4">
      <div>
        <p class="font-medium">{{ t('notifications.communications.language.title') }}</p>
        <p class="text-xs text-[var(--ui-text-muted)] mt-1 max-w-xl">
          {{ t('notifications.communications.language.help') }}
        </p>
      </div>
      <UFormField :label="t('notifications.communications.language.label')">
        <USelect v-model="language" :items="options" class="w-full max-w-xs" />
      </UFormField>
    </div>
    <template #footer>
      <div class="flex justify-end">
        <UButton color="primary" :loading="saving" @click="save">
          {{ t('notifications.communications.language.save') }}
        </UButton>
      </div>
    </template>
  </UCard>
</template>
