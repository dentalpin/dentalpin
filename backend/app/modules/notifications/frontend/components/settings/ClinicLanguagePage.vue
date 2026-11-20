<script setup lang="ts">
import { communicationLanguages } from '../../utils/communicationLanguages'

const { t } = useI18n()
const { settings, loading, saving, fetch, update } = useCommunicationsSettings()

const language = ref('es')

watch(settings, (s) => {
  if (s) language.value = communicationLanguages.find(item => item.value === s.language)?.value ?? 'es'
})

onMounted(fetch)

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
          :items="communicationLanguages"
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
