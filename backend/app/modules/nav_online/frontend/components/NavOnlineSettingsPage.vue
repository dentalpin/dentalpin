<script setup lang="ts">
import { useNavOnline, type NavSettings } from '../composables/useNavOnline'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { fetchSettings, saveSettings, testConnection } = useNavOnline()

const settings = ref<NavSettings | null>(null)
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)

const form = reactive({
  environment: 'test' as 'test' | 'prod',
  tax_number: '',
  technical_user_login: '',
  technical_user_password: '',
  signature_key: '',
  exchange_key: '',
  software_id: 'DENTALPIN-00000001',
  software_dev_contact: '',
  enabled: false
})

const envOptions = computed(() => [
  { value: 'test', label: t('nav_online.env.test') },
  { value: 'prod', label: t('nav_online.env.prod') }
])

onMounted(async () => {
  try {
    settings.value = await fetchSettings()
    const s = settings.value
    form.environment = s.environment
    form.tax_number = s.tax_number ?? ''
    form.technical_user_login = s.technical_user_login ?? ''
    form.software_id = s.software_id
    form.software_dev_contact = s.software_dev_contact ?? ''
    form.enabled = s.enabled
  } finally {
    loading.value = false
  }
})

async function onSave(toggleEnabled?: boolean) {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      environment: form.environment,
      tax_number: form.tax_number || null,
      technical_user_login: form.technical_user_login || null,
      software_id: form.software_id || null,
      software_dev_contact: form.software_dev_contact || null
    }
    // Secrets are write-only: only send what the user typed.
    if (form.technical_user_password) payload.technical_user_password = form.technical_user_password
    if (form.signature_key) payload.signature_key = form.signature_key
    if (form.exchange_key) payload.exchange_key = form.exchange_key
    if (toggleEnabled !== undefined) payload.enabled = toggleEnabled
    settings.value = await saveSettings(payload)
    form.enabled = settings.value.enabled
    form.technical_user_password = ''
    form.signature_key = ''
    form.exchange_key = ''
    toast.add({ title: t('nav_online.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('nav_online.saveError'), description: errorDetail(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function onTest() {
  testing.value = true
  try {
    const res = await testConnection()
    if (res.success) toast.add({ title: t('nav_online.testOk'), color: 'success' })
    else toast.add({ title: t('nav_online.testFail'), description: res.error ?? '', color: 'error' })
  } catch (e) {
    toast.add({ title: t('nav_online.testFail'), description: errorDetail(e), color: 'error' })
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('nav_online.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('nav_online.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="loading"
      class="h-40 w-full"
    />

    <template v-else>
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('nav_online.connection') }}</span>
            <UBadge
              :color="settings?.enabled ? 'success' : 'neutral'"
              variant="subtle"
            >
              {{ settings?.enabled ? t('nav_online.enabled') : t('nav_online.disabled') }}
            </UBadge>
          </div>
        </template>
        <div class="space-y-3">
          <UFormField :label="t('nav_online.environment')">
            <USelect
              v-model="form.environment"
              :items="envOptions"
              value-key="value"
              label-key="label"
              class="w-60"
            />
          </UFormField>
          <UFormField
            :label="t('nav_online.taxNumber')"
            :help="t('nav_online.taxNumberHelp')"
          >
            <UInput
              v-model="form.tax_number"
              placeholder="12345678"
              maxlength="11"
            />
          </UFormField>
          <UFormField :label="t('nav_online.login')">
            <UInput
              v-model="form.technical_user_login"
              maxlength="15"
            />
          </UFormField>
          <UFormField
            :label="t('nav_online.password')"
            :help="settings?.has_password ? t('nav_online.secretStored') : ''"
          >
            <UInput
              v-model="form.technical_user_password"
              type="password"
              autocomplete="off"
              :placeholder="settings?.has_password ? '••••••••' : ''"
            />
          </UFormField>
          <UFormField
            :label="t('nav_online.signatureKey')"
            :help="settings?.has_signature_key ? t('nav_online.secretStored') : ''"
          >
            <UInput
              v-model="form.signature_key"
              type="password"
              autocomplete="off"
              :placeholder="settings?.has_signature_key ? '••••••••' : ''"
            />
          </UFormField>
          <UFormField
            :label="t('nav_online.exchangeKey')"
            :help="settings?.has_exchange_key ? t('nav_online.secretStored') : t('nav_online.exchangeKeyHelp')"
          >
            <UInput
              v-model="form.exchange_key"
              type="password"
              autocomplete="off"
              maxlength="16"
              :placeholder="settings?.has_exchange_key ? '••••••••' : ''"
            />
          </UFormField>
          <UFormField
            :label="t('nav_online.softwareId')"
            :help="t('nav_online.softwareIdHelp')"
          >
            <UInput
              v-model="form.software_id"
              maxlength="18"
              class="font-mono"
            />
          </UFormField>
          <UFormField :label="t('nav_online.devContact')">
            <UInput
              v-model="form.software_dev_contact"
              placeholder="support@example.com"
            />
          </UFormField>
          <div class="flex flex-wrap gap-2">
            <UButton
              :loading="saving"
              icon="i-lucide-save"
              @click="onSave()"
            >
              {{ t('common.save') }}
            </UButton>
            <UButton
              variant="outline"
              icon="i-lucide-plug-zap"
              :loading="testing"
              @click="onTest"
            >
              {{ t('nav_online.testConnection') }}
            </UButton>
            <UButton
              v-if="!settings?.enabled"
              color="success"
              variant="soft"
              icon="i-lucide-power"
              :loading="saving"
              @click="onSave(true)"
            >
              {{ t('nav_online.enable') }}
            </UButton>
            <UButton
              v-else
              color="warning"
              variant="soft"
              icon="i-lucide-power-off"
              :loading="saving"
              @click="onSave(false)"
            >
              {{ t('nav_online.disable') }}
            </UButton>
          </div>
          <p
            v-if="settings?.last_error"
            class="text-xs text-red-500 break-all"
          >
            {{ settings.last_error }}
          </p>
        </div>
      </UCard>
    </template>
  </div>
</template>
