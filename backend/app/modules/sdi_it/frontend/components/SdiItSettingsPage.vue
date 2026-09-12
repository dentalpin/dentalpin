<script setup lang="ts">
import { useSdiIt, fmtWhen, type SdiSettings } from '../composables/useSdiIt'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const { fetchSettings, saveSettings, testPec } = useSdiIt()

const settings = ref<SdiSettings | null>(null)
const loading = ref(true)
const saving = ref(false)
const testing = ref(false)

const form = reactive({
  transport: 'manual' as 'manual' | 'pec',
  regime_fiscale: 'RF01',
  bollo_virtuale: true,
  riferimento_normativo: '',
  pec_address: '',
  sdi_pec_address: '',
  smtp_host: '',
  smtp_port: 465,
  smtp_username: '',
  smtp_password: '',
  imap_host: '',
  imap_port: 993,
  imap_folder: 'INBOX'
})

const transportOptions = computed(() => [
  { value: 'manual', label: t('sdi_it.transportOpt.manual') },
  { value: 'pec', label: t('sdi_it.transportOpt.pec') }
])
const regimeOptions = ['RF01', 'RF02', 'RF04', 'RF05', 'RF06', 'RF07', 'RF08', 'RF09', 'RF10', 'RF11', 'RF12', 'RF13', 'RF14', 'RF15', 'RF16', 'RF17', 'RF18', 'RF19'].map(v => ({
  value: v,
  label: v === 'RF01' ? 'RF01 · ordinario' : v === 'RF19' ? 'RF19 · forfettario' : v
}))

function fill(s: SdiSettings) {
  form.transport = s.transport
  form.regime_fiscale = s.regime_fiscale
  form.bollo_virtuale = s.bollo_virtuale
  form.riferimento_normativo = s.riferimento_normativo
  form.pec_address = s.pec_address ?? ''
  form.sdi_pec_address = s.sdi_pec_address
  form.smtp_host = s.smtp_host ?? ''
  form.smtp_port = s.smtp_port
  form.smtp_username = s.smtp_username ?? ''
  form.imap_host = s.imap_host ?? ''
  form.imap_port = s.imap_port
  form.imap_folder = s.imap_folder
}

onMounted(async () => {
  try {
    settings.value = await fetchSettings()
    fill(settings.value)
  } finally {
    loading.value = false
  }
})

async function onSave(toggleEnabled?: boolean) {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      transport: form.transport,
      regime_fiscale: form.regime_fiscale,
      bollo_virtuale: form.bollo_virtuale,
      riferimento_normativo: form.riferimento_normativo || null,
      pec_address: form.pec_address || null,
      sdi_pec_address: form.sdi_pec_address || null,
      smtp_host: form.smtp_host || null,
      smtp_port: form.smtp_port || null,
      smtp_username: form.smtp_username || null,
      imap_host: form.imap_host || null,
      imap_port: form.imap_port || null,
      imap_folder: form.imap_folder || null
    }
    // The password is write-only: only send what the user typed.
    if (form.smtp_password) payload.smtp_password = form.smtp_password
    if (toggleEnabled !== undefined) payload.enabled = toggleEnabled
    settings.value = await saveSettings(payload)
    fill(settings.value)
    form.smtp_password = ''
    toast.add({ title: t('sdi_it.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('sdi_it.saveError'), description: errorDetail(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function onTest() {
  testing.value = true
  try {
    const res = await testPec()
    const ok = res.smtp === 'ok' && res.imap === 'ok'
    toast.add({
      title: ok ? t('sdi_it.testOk') : t('sdi_it.testFail'),
      description: `SMTP: ${res.smtp} · IMAP: ${res.imap}`,
      color: ok ? 'success' : 'error'
    })
  } catch (e) {
    toast.add({ title: t('sdi_it.testFail'), description: errorDetail(e), color: 'error' })
  } finally {
    testing.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-2xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('sdi_it.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('sdi_it.settings.description') }}
      </p>
    </div>

    <USkeleton
      v-if="loading"
      class="h-40 w-full"
    />

    <template v-else>
      <UAlert
        icon="i-lucide-info"
        color="info"
        variant="subtle"
        :title="t('sdi_it.scope.title')"
        :description="t('sdi_it.scope.text')"
      />

      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('sdi_it.invoiceData') }}</span>
            <UBadge
              :color="settings?.enabled ? 'success' : 'neutral'"
              variant="subtle"
            >
              {{ settings?.enabled ? t('sdi_it.enabled') : t('sdi_it.disabled') }}
            </UBadge>
          </div>
        </template>
        <div class="space-y-3">
          <UFormField
            :label="t('sdi_it.regime')"
            :help="t('sdi_it.regimeHelp')"
          >
            <USelect
              v-model="form.regime_fiscale"
              :items="regimeOptions"
              value-key="value"
              label-key="label"
              class="w-60"
            />
          </UFormField>
          <UFormField
            :label="t('sdi_it.riferimento')"
            :help="t('sdi_it.riferimentoHelp')"
          >
            <UInput
              v-model="form.riferimento_normativo"
              maxlength="100"
              class="w-full"
            />
          </UFormField>
          <UCheckbox
            v-model="form.bollo_virtuale"
            :label="t('sdi_it.bollo')"
            :description="t('sdi_it.bolloHelp')"
          />
          <p class="text-xs text-subtle">
            {{ t('sdi_it.progressivo', { n: settings?.progressivo_invio ?? 0 }) }}
          </p>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <span class="font-medium">{{ t('sdi_it.transportLabel') }}</span>
        </template>
        <div class="space-y-3">
          <UFormField :label="t('sdi_it.transportLabel')">
            <USelect
              v-model="form.transport"
              :items="transportOptions"
              value-key="value"
              label-key="label"
              class="w-72"
            />
          </UFormField>
          <p class="text-xs text-subtle">
            {{ form.transport === 'pec' ? t('sdi_it.transportOpt.pecHelp') : t('sdi_it.transportOpt.manualHelp') }}
          </p>

          <template v-if="form.transport === 'pec'">
            <UFormField :label="t('sdi_it.pec.address')">
              <UInput
                v-model="form.pec_address"
                type="email"
                placeholder="studio@pec.example.it"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('sdi_it.pec.sdiAddress')"
              :help="t('sdi_it.pec.sdiAddressHelp')"
            >
              <UInput
                v-model="form.sdi_pec_address"
                class="w-full font-mono"
              />
            </UFormField>
            <div class="grid grid-cols-1 md:grid-cols-[1fr_8rem] gap-3">
              <UFormField :label="t('sdi_it.pec.smtpHost')">
                <UInput
                  v-model="form.smtp_host"
                  placeholder="smtps.pec.example.it"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('sdi_it.pec.port')">
                <UInput
                  v-model.number="form.smtp_port"
                  type="number"
                />
              </UFormField>
              <UFormField :label="t('sdi_it.pec.imapHost')">
                <UInput
                  v-model="form.imap_host"
                  placeholder="imaps.pec.example.it"
                  class="w-full"
                />
              </UFormField>
              <UFormField :label="t('sdi_it.pec.port')">
                <UInput
                  v-model.number="form.imap_port"
                  type="number"
                />
              </UFormField>
            </div>
            <UFormField :label="t('sdi_it.pec.username')">
              <UInput
                v-model="form.smtp_username"
                autocomplete="off"
                class="w-full"
              />
            </UFormField>
            <UFormField
              :label="t('sdi_it.pec.password')"
              :help="settings?.has_smtp_password ? t('sdi_it.secretStored') : ''"
            >
              <UInput
                v-model="form.smtp_password"
                type="password"
                autocomplete="off"
                :placeholder="settings?.has_smtp_password ? '••••••••' : ''"
                class="w-full"
              />
            </UFormField>
            <UFormField :label="t('sdi_it.pec.folder')">
              <UInput
                v-model="form.imap_folder"
                class="w-60"
              />
            </UFormField>
            <p
              v-if="settings?.last_pec_poll_at"
              class="text-xs text-subtle"
            >
              {{ t('sdi_it.pec.lastPoll', { at: fmtWhen(settings.last_pec_poll_at) }) }}
            </p>
          </template>

          <div class="flex flex-wrap gap-2">
            <UButton
              :loading="saving"
              icon="i-lucide-save"
              @click="onSave()"
            >
              {{ t('common.save') }}
            </UButton>
            <UButton
              v-if="form.transport === 'pec'"
              variant="outline"
              icon="i-lucide-plug-zap"
              :loading="testing"
              @click="onTest"
            >
              {{ t('sdi_it.testConnection') }}
            </UButton>
            <UButton
              v-if="!settings?.enabled"
              color="success"
              variant="soft"
              icon="i-lucide-power"
              :loading="saving"
              @click="onSave(true)"
            >
              {{ t('sdi_it.enable') }}
            </UButton>
            <UButton
              v-else
              color="warning"
              variant="soft"
              icon="i-lucide-power-off"
              :loading="saving"
              @click="onSave(false)"
            >
              {{ t('sdi_it.disable') }}
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
