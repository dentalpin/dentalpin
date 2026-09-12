<script setup lang="ts">
import { useSistemaTs, fmtWhen, fmtDate, TIPI_SPESA, type TsSettings, type ItemType } from '../composables/useSistemaTs'
import { errorDetail } from '~~/app/utils/error'

const { t } = useI18n()
const toast = useToast()
const api = useApi()
const { fetchSettings, saveSettings, fetchItemTypes, setItemType } = useSistemaTs()

const settings = ref<TsSettings | null>(null)
const loading = ref(true)
const saving = ref(false)

const form = reactive({
  environment: 'test' as 'test' | 'prod',
  username: '',
  password: '',
  pincode: '',
  cf_proprietario: '',
  codice_regione: '',
  codice_asl: '',
  codice_ssa: '',
  dispositivo: '1',
  default_tipo_spesa: 'SR',
  sync_from: '' as string,
  certificate_b64: ''
})

const envOptions = computed(() => [
  { value: 'test', label: t('sistema_ts.env.test') },
  { value: 'prod', label: t('sistema_ts.env.prod') }
])
const tipoOptions = computed(() => TIPI_SPESA.map(v => ({ value: v as string, label: `${v} · ${t(`sistema_ts.tipoSpesa.${v}`)}` })))

function fill(s: TsSettings) {
  form.environment = s.environment
  form.username = s.username ?? ''
  form.cf_proprietario = s.cf_proprietario ?? ''
  form.codice_regione = s.codice_regione ?? ''
  form.codice_asl = s.codice_asl ?? ''
  form.codice_ssa = s.codice_ssa ?? ''
  form.dispositivo = s.dispositivo
  form.default_tipo_spesa = s.default_tipo_spesa
  form.sync_from = s.sync_from ?? ''
}

// Catalog items × tipoSpesa mapping
interface CatalogItem { id: string, internal_code: string, names: Record<string, string> }
const items = ref<CatalogItem[]>([])
const itemTypes = ref<Record<string, ItemType>>({})
const { locale } = useI18n()

function itemName(i: CatalogItem): string {
  return i.names?.[locale.value] ?? i.names?.en ?? i.names?.es ?? Object.values(i.names ?? {})[0] ?? i.internal_code
}

async function loadItems() {
  try {
    const res = await api.get<{ data: CatalogItem[] }>('/api/v1/catalog/items', { query: { page_size: 500, is_active: true } })
    items.value = res.data
    const types = await fetchItemTypes()
    itemTypes.value = Object.fromEntries(types.map(x => [x.catalog_item_id, x]))
  } catch {
    items.value = []
  }
}

async function onItemType(item: CatalogItem, tipo: string) {
  try {
    const saved = await setItemType(item.id, tipo)
    itemTypes.value = { ...itemTypes.value, [item.id]: saved }
  } catch (e) {
    toast.add({ title: t('sistema_ts.saveError'), description: errorDetail(e), color: 'error' })
  }
}

onMounted(async () => {
  try {
    settings.value = await fetchSettings()
    fill(settings.value)
    await loadItems()
  } finally {
    loading.value = false
  }
})

async function onCertificateFile(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  const buf = await file.arrayBuffer()
  let bin = ''
  for (const b of new Uint8Array(buf)) bin += String.fromCharCode(b)
  form.certificate_b64 = btoa(bin)
}

async function onSave(toggleEnabled?: boolean) {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      environment: form.environment,
      username: form.username || null,
      cf_proprietario: form.cf_proprietario || null,
      codice_regione: form.codice_regione || null,
      codice_asl: form.codice_asl || null,
      codice_ssa: form.codice_ssa || null,
      dispositivo: form.dispositivo || null,
      default_tipo_spesa: form.default_tipo_spesa,
      sync_from: form.sync_from || null
    }
    // Secrets are write-only: only send what the user typed.
    if (form.password) payload.password = form.password
    if (form.pincode) payload.pincode = form.pincode
    if (form.certificate_b64) payload.certificate_b64 = form.certificate_b64
    if (toggleEnabled !== undefined) payload.enabled = toggleEnabled
    settings.value = await saveSettings(payload)
    fill(settings.value)
    form.password = ''
    form.pincode = ''
    form.certificate_b64 = ''
    toast.add({ title: t('sistema_ts.saved'), color: 'success' })
  } catch (e) {
    toast.add({ title: t('sistema_ts.saveError'), description: errorDetail(e), color: 'error' })
  } finally {
    saving.value = false
  }
}

async function onClearCertificate() {
  saving.value = true
  try {
    settings.value = await saveSettings({ clear_certificate: true })
    toast.add({ title: t('sistema_ts.saved'), color: 'success' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <div>
      <h2 class="text-lg font-semibold">
        {{ t('sistema_ts.settings.title') }}
      </h2>
      <p class="text-sm text-gray-500">
        {{ t('sistema_ts.settings.description') }}
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
        :title="t('sistema_ts.scope.title')"
        :description="t('sistema_ts.scope.text')"
      />

      <!-- Year overview -->
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <span class="font-medium">{{ t('sistema_ts.year.title', { year: settings?.year }) }}</span>
            <UBadge
              :color="settings?.enabled ? 'success' : 'neutral'"
              variant="subtle"
            >
              {{ settings?.enabled ? t('sistema_ts.enabled') : t('sistema_ts.disabled') }}
            </UBadge>
          </div>
        </template>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <div class="text-subtle text-xs uppercase tracking-wide">
              {{ t('sistema_ts.year.deadline') }}
            </div>
            <div class="font-medium">
              {{ fmtDate(settings?.deadline) }}
            </div>
          </div>
          <div>
            <div class="text-subtle text-xs uppercase tracking-wide">
              {{ t('sistema_ts.year.unsent') }}
            </div>
            <div
              class="font-medium"
              :class="settings?.unsent_count ? 'text-amber-600' : ''"
            >
              {{ settings?.unsent_count ?? 0 }}
            </div>
          </div>
          <div>
            <div class="text-subtle text-xs uppercase tracking-wide">
              {{ t('sistema_ts.year.accepted') }}
            </div>
            <div class="font-medium text-green-600">
              {{ settings?.accepted_count ?? 0 }}
            </div>
          </div>
          <div>
            <div class="text-subtle text-xs uppercase tracking-wide">
              {{ t('sistema_ts.year.rejected') }}
            </div>
            <div
              class="font-medium"
              :class="settings?.rejected_count ? 'text-red-500' : ''"
            >
              {{ settings?.rejected_count ?? 0 }}
            </div>
          </div>
        </div>
        <p
          v-if="settings?.last_response_at"
          class="text-xs text-subtle mt-3"
        >
          {{ t('sistema_ts.year.lastResponse', { at: fmtWhen(settings.last_response_at) }) }}
        </p>
        <p
          v-if="settings?.last_error"
          class="text-xs text-red-500 break-all mt-1"
        >
          {{ settings.last_error }}
        </p>
      </UCard>

      <!-- Credentials -->
      <UCard>
        <template #header>
          <span class="font-medium">{{ t('sistema_ts.credentials') }}</span>
        </template>
        <div class="space-y-3">
          <UFormField :label="t('sistema_ts.environment')">
            <USelect
              v-model="form.environment"
              :items="envOptions"
              value-key="value"
              label-key="label"
              class="w-60"
            />
          </UFormField>
          <UFormField
            :label="t('sistema_ts.username')"
            :help="t('sistema_ts.usernameHelp')"
          >
            <UInput
              v-model="form.username"
              maxlength="16"
              class="w-full font-mono"
              autocomplete="off"
            />
          </UFormField>
          <UFormField
            :label="t('sistema_ts.password')"
            :help="settings?.has_password ? t('sistema_ts.secretStored') : ''"
          >
            <UInput
              v-model="form.password"
              type="password"
              autocomplete="off"
              :placeholder="settings?.has_password ? '••••••••' : ''"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('sistema_ts.pincode')"
            :help="settings?.has_pincode ? t('sistema_ts.secretStored') : t('sistema_ts.pincodeHelp')"
          >
            <UInput
              v-model="form.pincode"
              type="password"
              autocomplete="off"
              :placeholder="settings?.has_pincode ? '••••••••' : ''"
              class="w-full"
            />
          </UFormField>
          <UFormField
            :label="t('sistema_ts.certificate')"
            :help="settings?.has_custom_certificate ? t('sistema_ts.certificateCustom', { at: fmtWhen(settings?.certificate_expires_at) }) : t('sistema_ts.certificateVendored', { at: fmtWhen(settings?.certificate_expires_at) })"
          >
            <div class="flex flex-wrap items-center gap-2">
              <input
                type="file"
                accept=".cer,.crt,.pem,.der"
                class="text-xs"
                @change="onCertificateFile"
              >
              <UButton
                v-if="settings?.has_custom_certificate"
                size="xs"
                variant="ghost"
                icon="i-lucide-undo-2"
                :loading="saving"
                @click="onClearCertificate"
              >
                {{ t('sistema_ts.certificateReset') }}
              </UButton>
            </div>
          </UFormField>
        </div>
      </UCard>

      <!-- Identity -->
      <UCard>
        <template #header>
          <span class="font-medium">{{ t('sistema_ts.identity') }}</span>
        </template>
        <div class="space-y-3">
          <UFormField
            :label="t('sistema_ts.cfProprietario')"
            :help="t('sistema_ts.cfProprietarioHelp')"
          >
            <UInput
              v-model="form.cf_proprietario"
              maxlength="16"
              class="w-full font-mono uppercase"
            />
          </UFormField>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <UFormField :label="t('sistema_ts.codiceRegione')">
              <UInput
                v-model="form.codice_regione"
                maxlength="3"
              />
            </UFormField>
            <UFormField :label="t('sistema_ts.codiceAsl')">
              <UInput
                v-model="form.codice_asl"
                maxlength="3"
              />
            </UFormField>
            <UFormField :label="t('sistema_ts.codiceSsa')">
              <UInput
                v-model="form.codice_ssa"
                maxlength="10"
              />
            </UFormField>
          </div>
          <p class="text-xs text-subtle">
            {{ t('sistema_ts.structureHelp') }}
          </p>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-3">
            <UFormField
              :label="t('sistema_ts.dispositivo')"
              :help="t('sistema_ts.dispositivoHelp')"
            >
              <UInput
                v-model="form.dispositivo"
                maxlength="10"
              />
            </UFormField>
            <UFormField :label="t('sistema_ts.defaultTipoSpesa')">
              <USelect
                v-model="form.default_tipo_spesa"
                :items="tipoOptions"
                value-key="value"
                label-key="label"
              />
            </UFormField>
            <UFormField
              :label="t('sistema_ts.syncFrom')"
              :help="t('sistema_ts.syncFromHelp')"
            >
              <UInput
                v-model="form.sync_from"
                type="date"
              />
            </UFormField>
          </div>

          <div class="flex flex-wrap gap-2">
            <UButton
              :loading="saving"
              icon="i-lucide-save"
              @click="onSave()"
            >
              {{ t('common.save') }}
            </UButton>
            <UButton
              v-if="!settings?.enabled"
              color="success"
              variant="soft"
              icon="i-lucide-power"
              :loading="saving"
              @click="onSave(true)"
            >
              {{ t('sistema_ts.enable') }}
            </UButton>
            <UButton
              v-else
              color="warning"
              variant="soft"
              icon="i-lucide-power-off"
              :loading="saving"
              @click="onSave(false)"
            >
              {{ t('sistema_ts.disable') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <!-- tipoSpesa per catalog item -->
      <UCard>
        <template #header>
          <div>
            <span class="font-medium">{{ t('sistema_ts.itemTypes.title') }}</span>
            <p class="text-xs text-subtle">
              {{ t('sistema_ts.itemTypes.help', { default: form.default_tipo_spesa }) }}
            </p>
          </div>
        </template>
        <div
          v-if="!items.length"
          class="text-sm text-subtle"
        >
          {{ t('sistema_ts.itemTypes.empty') }}
        </div>
        <div
          v-else
          class="overflow-x-auto"
        >
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-gray-500 border-b border-[var(--ui-border)]">
                <th class="py-2 pr-2">
                  {{ t('sistema_ts.itemTypes.item') }}
                </th>
                <th class="py-2 pr-2 w-64">
                  {{ t('sistema_ts.itemTypes.tipoSpesa') }}
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in items"
                :key="item.id"
                class="border-b border-[var(--ui-border)] last:border-0"
              >
                <td class="py-2 pr-2">
                  <span class="font-mono text-xs text-subtle mr-2">{{ item.internal_code }}</span>{{ itemName(item) }}
                </td>
                <td class="py-2 pr-2">
                  <USelect
                    :model-value="itemTypes[item.id]?.tipo_spesa ?? form.default_tipo_spesa"
                    :items="tipoOptions"
                    value-key="value"
                    label-key="label"
                    class="w-full"
                    @update:model-value="(v: string) => onItemType(item, v)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>
    </template>
  </div>
</template>
