<template>
  <div class="space-y-6">
    <div>
      <h2 class="font-semibold text-default">
        {{ t('sms_gateway.settings.title') }}
      </h2>
      <p class="text-caption text-subtle">
        {{ t('sms_gateway.settings.description') }}
      </p>
    </div>

    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton class="h-10 w-full" />
      <USkeleton class="h-10 w-full" />
    </div>

    <UAlert
      v-else-if="error"
      color="error"
      :title="t('sms_gateway.common.loadError')"
      :actions="[{ label: t('sms_gateway.common.retry'), onClick: fetchAll }]"
    />

    <div
      v-else
      class="space-y-4"
    >
      <UFormField :label="t('sms_gateway.settings.provider')">
        <USelect
          v-model="form.provider"
          :items="providerOptions"
          class="w-full sm:w-64"
        />
      </UFormField>

      <UFormField :label="t('sms_gateway.settings.fromNumber')">
        <UInput
          v-model="form.from_number"
          dir="ltr"
          placeholder="+34..."
          class="w-full sm:w-64"
        />
      </UFormField>

      <div class="flex items-start gap-3">
        <USwitch v-model="form.is_active" />
        <div>
          <p class="text-sm font-medium text-default">
            {{ t('sms_gateway.settings.active') }}
          </p>
          <p class="text-caption text-subtle">
            {{ t('sms_gateway.settings.activeHelp') }}
          </p>
        </div>
      </div>

      <UAlert
        color="warning"
        :title="t('sms_gateway.settings.placeholderNote')"
      />

      <div class="flex flex-wrap gap-2">
        <UButton
          icon="i-lucide-save"
          :loading="saving"
          @click="onSave"
        >
          {{ t('sms_gateway.common.save') }}
        </UButton>
        <UButton
          variant="outline"
          icon="i-lucide-flask-conical"
          :loading="testing"
          @click="onTest"
        >
          {{ t('sms_gateway.settings.test') }}
        </UButton>
      </div>

      <UAlert
        v-if="testResult"
        :color="testResult.would_send ? 'success' : 'neutral'"
        :title="testResult.note ?? t('sms_gateway.settings.testResult', { configured: testResult.configured, wouldSend: testResult.would_send })"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { errorMessage } from '~~/app/utils/error'
import { useSmsGateway } from '../composables/useSmsGateway'

const { t } = useI18n()
const toast = useToast()
const { fetchSettings, saveSettings, listProviders, testConnection } = useSmsGateway()

const loading = ref(true)
const error = ref(false)
const saving = ref(false)
const testing = ref(false)
const providers = ref<string[]>([])
const testResult = ref<{ configured: boolean, would_send: boolean, note?: string | null } | null>(null)
const form = reactive({
  provider: 'log',
  from_number: '',
  is_active: false
})

const providerOptions = computed(() =>
  providers.value.map(p => ({ label: p, value: p }))
)

async function fetchAll() {
  loading.value = true
  error.value = false
  try {
    const [s, plist] = await Promise.all([fetchSettings(), listProviders()])
    providers.value = plist.data
    form.provider = s.data.provider
    form.from_number = s.data.from_number ?? ''
    form.is_active = s.data.is_active
  } catch (e) {
    error.value = true
    toast.add({ title: t('sms_gateway.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    loading.value = false
  }
}

async function onSave() {
  saving.value = true
  try {
    await saveSettings({
      provider: form.provider,
      from_number: form.from_number || null,
      is_active: form.is_active
    })
    toast.add({ title: t('sms_gateway.common.saved'), color: 'success' })
    await fetchAll()
  } catch (e) {
    toast.add({ title: t('sms_gateway.common.saveError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function onTest() {
  testing.value = true
  testResult.value = null
  try {
    testResult.value = (await testConnection()).data
  } catch (e) {
    toast.add({ title: t('sms_gateway.common.loadError'), description: errorMessage(e, ''), color: 'error' })
  } finally {
    testing.value = false
  }
}

onMounted(fetchAll)
</script>
