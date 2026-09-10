<script setup lang="ts">
const { t } = useI18n()
const { settings, loading, saving, fetch, update } = useCommunicationsSettings()

const language = ref<'ar' | 'es' | 'en' | 'fr' | 'pt' | 'ta'>('ar')

const SUPPORTED = ['ar', 'es', 'en', 'fr', 'pt', 'ta'] as const

watch(settings, (s) => {
  if (s) language.value = (SUPPORTED.includes(s.language as typeof SUPPORTED[number]) ? s.language as typeof language.value : 'ar')
})

onMounted(fetch)

const options = [
  { value: 'ar', label: 'العربية' },
  { value: 'es', label: 'Español' },
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'Français' },
  { value: 'pt', label: 'Português' },
  { value: 'ta', label: 'தமிழ்' }
]

async function save() {
  await update({ language: language.value })
}
</script>

<template>
  <UCard v-if="!loading">
    <div class="space-y-4">
      <div>
        <p class="font-medium">
          {{ t('notifications.communications.language.title') }}
        </p>
        <p class="text-xs text-[var(--ui-text-muted)] mt-1 max-w-xl">
          {{ t('notifications.communications.language.help') }}
        </p>
      </div>
      <UFormField :label="t('notifications.communications.language.label')">
        <USelect
          v-model="language"
          :items="options"
          class="w-full max-w-xs"
        />
      </UFormField>
    </div>
    <template #footer>
      <div class="flex justify-end">
        <UButton
          color="primary"
          :loading="saving"
          @click="save"
        >
          {{ t('notifications.communications.language.save') }}
        </UButton>
      </div>
    </template>
  </UCard>
</template>
