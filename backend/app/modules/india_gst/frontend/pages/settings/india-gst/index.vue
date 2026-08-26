<script setup lang="ts">
// India GST settings — a single page with sections, following
// verifactu's precedent of a fully custom settings page (not wrapped
// in the host's generic SettingsLayout/SettingsSection).

import type { IndiaGstMissingSacItem, IndiaGstSettings } from '../../../composables/useIndiaGst'
import { PERMISSIONS } from '~~/app/config/permissions'

definePageMeta({ layout: 'default' })

const { t, locale } = useI18n()
const toast = useToast()
const { can } = usePermissions()

// Read-only view for roles with settings.read; every mutating control
// needs settings.configure (verifactu's canManage pattern).
const canManage = computed(() => can(PERMISSIONS.indiaGst.settingsConfigure))
const canManageCatalog = computed(() => can(PERMISSIONS.indiaGst.catalogManage))
const { options: stateOptions } = useIndiaGstStates()
const {
  getSettings,
  updateSettings,
  getCatalogDefaults,
  autoconfigureCatalogDefaults,
  updateCatalogDefault
} = useIndiaGst()

const isLoading = ref(true)
const isSaving = ref(false)
const settings = ref<IndiaGstSettings | null>(null)

const form = ref({
  trade_name: '',
  gstin: '',
  registration_type: 'regular' as 'regular' | 'composition' | 'unregistered' | 'exempt',
  clinic_state: undefined as string | undefined,
  turnover_threshold: null as number | null,
  show_gstin_on_invoice: true,
  show_sac_on_invoice: true
})

// Live hint (mirrors the API's gstin_state_mismatch flag): the GSTIN's
// leading two digits are the supplier's state code — a disagreement
// with clinic_state silently flips intra/inter-state classification
// (#262). Warn, never block.
const gstinStateMismatch = computed(() => {
  const gstin = (form.value.gstin || '').trim()
  return gstin.length >= 2 && !!form.value.clinic_state
    && gstin.slice(0, 2) !== form.value.clinic_state
})

const registrationOptions = [
  { label: t('indiaGst.settings.registrationRegular'), value: 'regular' },
  { label: t('indiaGst.settings.registrationComposition'), value: 'composition' },
  { label: t('indiaGst.settings.registrationUnregistered'), value: 'unregistered' },
  { label: t('indiaGst.settings.registrationExempt'), value: 'exempt' }
]

const missingSac = ref<IndiaGstMissingSacItem[]>([])
const sacDrafts = ref<Record<string, string>>({})
const isAutoconfiguring = ref(false)

// Treatment names are a per-locale dict on the catalog item, so resolve
// them against the viewer's own UI language instead of whatever the
// backend happens to pick. English is the fallback for locales the
// catalog has no translation for.
function treatmentName(item: IndiaGstMissingSacItem): string {
  return item.names?.[locale.value]
    || item.names?.en
    || item.name
    || item.internal_code
    || ''
}

onMounted(async () => {
  try {
    settings.value = await getSettings()
    form.value = {
      trade_name: settings.value.trade_name ?? '',
      gstin: settings.value.gstin ?? '',
      registration_type: settings.value.registration_type,
      clinic_state: settings.value.clinic_state ?? undefined,
      turnover_threshold: settings.value.turnover_threshold ? Number(settings.value.turnover_threshold) : null,
      show_gstin_on_invoice: settings.value.show_gstin_on_invoice,
      show_sac_on_invoice: settings.value.show_sac_on_invoice
    }
    const catalogDefaults = await getCatalogDefaults()
    missingSac.value = catalogDefaults.missing
  } catch {
    toast.add({ title: t('common.error'), description: t('indiaGst.settings.loadError'), color: 'error' })
  } finally {
    isLoading.value = false
  }
})

async function save() {
  isSaving.value = true
  try {
    settings.value = await updateSettings({
      trade_name: form.value.trade_name || null,
      gstin: form.value.gstin || null,
      registration_type: form.value.registration_type,
      clinic_state: form.value.clinic_state ?? null,
      turnover_threshold: form.value.turnover_threshold != null ? String(form.value.turnover_threshold) : null,
      show_gstin_on_invoice: form.value.show_gstin_on_invoice,
      show_sac_on_invoice: form.value.show_sac_on_invoice
    })
    toast.add({ title: t('common.success'), description: t('indiaGst.settings.saved'), color: 'success' })
  } catch {
    toast.add({ title: t('common.error'), description: t('indiaGst.settings.saveError'), color: 'error' })
  } finally {
    isSaving.value = false
  }
}

async function autoconfigure() {
  isAutoconfiguring.value = true
  try {
    const result = await autoconfigureCatalogDefaults()
    missingSac.value = (await getCatalogDefaults()).missing
    toast.add({
      title: t('common.success'),
      description: t('indiaGst.settings.autoconfigureDone', {
        count: result.configured_count,
        sac: result.sac_code
      }),
      color: 'success'
    })
  } catch {
    toast.add({
      title: t('common.error'),
      description: t('indiaGst.settings.autoconfigureError'),
      color: 'error'
    })
  } finally {
    isAutoconfiguring.value = false
  }
}

async function saveSac(catalogItemId: string) {
  const sac = sacDrafts.value[catalogItemId]
  if (!sac) return
  await updateCatalogDefault(catalogItemId, sac)
  missingSac.value = missingSac.value.filter(m => m.catalog_item_id !== catalogItemId)
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <h1 class="text-display text-default">
      {{ t('indiaGst.settings.title') }}
    </h1>
    <p class="text-subtle">
      {{ t('indiaGst.settings.description') }}
    </p>

    <USkeleton
      v-if="isLoading"
      class="h-96 w-full"
    />

    <template v-else>
      <!-- Group 1: Clinic GST details -->
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.settings.clinicDetails') }}
          </h3>
        </template>
        <div class="space-y-4">
          <p
            v-if="form.registration_type !== 'regular'"
            class="text-caption text-warning"
          >
            {{ t('indiaGst.settings.nonRegularNotice') }}
          </p>
          <UFormField :label="t('indiaGst.settings.tradeName')">
            <UInput v-model="form.trade_name" />
          </UFormField>
          <UFormField
            :label="t('indiaGst.settings.gstin')"
            :hint="t('indiaGst.settings.gstinHint')"
          >
            <UInput
              v-model="form.gstin"
              placeholder="33ABCDE1234F1Z7"
            />
          </UFormField>
          <UFormField :label="t('indiaGst.settings.registrationType')">
            <USelectMenu
              v-model="form.registration_type"
              :items="registrationOptions"
              value-key="value"
            />
          </UFormField>
          <UFormField :label="t('indiaGst.settings.clinicState')">
            <USelectMenu
              v-model="form.clinic_state"
              :items="stateOptions"
              value-key="value"
              :placeholder="t('indiaGst.form.selectState')"
            />
          </UFormField>
          <p
            v-if="gstinStateMismatch"
            class="text-caption text-warning"
          >
            {{ t('indiaGst.settings.gstinStateMismatch') }}
          </p>
        </div>
      </UCard>

      <!-- Group 3: Catalog GST defaults -->
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.settings.catalogDefaults') }}
          </h3>
        </template>
        <div class="space-y-4">
          <div
            v-if="missingSac.length === 0"
            class="text-caption text-subtle"
          >
            {{ t('indiaGst.settings.allSacConfigured') }}
          </div>
          <div
            v-else
            class="space-y-2"
          >
            <div class="flex items-center justify-between gap-3">
              <p class="text-caption text-subtle">
                {{ t('indiaGst.settings.missingSacCount', { count: missingSac.length }) }}
              </p>
              <UButton
                v-if="canManageCatalog"
                size="xs"
                variant="soft"
                icon="i-lucide-wand-2"
                :loading="isAutoconfiguring"
                @click="autoconfigure"
              >
                {{ t('indiaGst.settings.autoconfigure') }}
              </UButton>
            </div>
            <p class="text-caption text-subtle">
              {{ t('indiaGst.settings.autoconfigureHint') }}
            </p>
            <div
              v-for="item in missingSac"
              :key="item.catalog_item_id"
              class="flex items-center gap-2"
            >
              <span class="flex-1 text-sm">{{ treatmentName(item) }}</span>
              <UInput
                v-model="sacDrafts[item.catalog_item_id]"
                size="xs"
                class="w-28"
                placeholder="999312"
                :disabled="!canManageCatalog"
              />
              <UButton
                v-if="canManageCatalog"
                size="xs"
                variant="soft"
                @click="saveSac(item.catalog_item_id)"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </div>
        </div>
      </UCard>

      <!-- Group 4: E-invoice integration -->
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.settings.einvoiceIntegration') }}
          </h3>
        </template>
        <div class="space-y-4">
          <UAlert
            color="neutral"
            variant="subtle"
            icon="i-lucide-info"
            :description="t('indiaGst.settings.einvoiceProfessionalNotice')"
          />
          <UFormField
            :label="t('indiaGst.settings.turnoverThreshold')"
            :hint="t('indiaGst.settings.turnoverThresholdHint')"
          >
            <UInput
              v-model.number="form.turnover_threshold"
              type="number"
            />
          </UFormField>
          <UBadge
            color="neutral"
            variant="subtle"
          >
            {{ t('indiaGst.settings.einvoiceNotConfigured') }}
          </UBadge>
        </div>
      </UCard>

      <!-- Group 5: Display options -->
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.settings.displayOptions') }}
          </h3>
        </template>
        <div class="space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ t('indiaGst.settings.showGstin') }}</span>
            <USwitch v-model="form.show_gstin_on_invoice" />
          </div>
          <div class="flex items-center justify-between">
            <span class="text-sm">{{ t('indiaGst.settings.showSac') }}</span>
            <USwitch v-model="form.show_sac_on_invoice" />
          </div>
        </div>
      </UCard>

      <!-- Group 6: Credit note workflow (informational) -->
      <UCard>
        <template #header>
          <h3 class="font-semibold text-default">
            {{ t('indiaGst.settings.creditNoteWorkflow') }}
          </h3>
        </template>
        <p class="text-caption text-subtle">
          {{ t('indiaGst.settings.creditNoteWorkflowDescription') }}
        </p>
      </UCard>

      <UButton
        v-if="canManage"
        block
        color="primary"
        :loading="isSaving"
        @click="save"
      >
        {{ t('common.save') }}
      </UButton>
    </template>
  </div>
</template>
