<script setup lang="ts">
import type { ClinicAddress, ClinicUpdate } from '~/types'
import { SUPPORTED_CURRENCIES } from '~/constants/currencies'
import { PERMISSIONS } from '~/config/permissions'

const { t } = useI18n()
const clinic = useClinic()
const { can } = usePermissions()
const canEdit = computed(() => can(PERMISSIONS.admin.clinicWrite))

const COUNTRY_CODES = [
  'AD', 'AE', 'AF', 'AG', 'AL', 'AM', 'AO', 'AR', 'AT', 'AU', 'AZ',
  'BA', 'BB', 'BD', 'BE', 'BF', 'BG', 'BH', 'BI', 'BJ', 'BN', 'BO', 'BR', 'BS', 'BT', 'BW', 'BY', 'BZ',
  'CA', 'CD', 'CF', 'CG', 'CH', 'CI', 'CL', 'CM', 'CN', 'CO', 'CR', 'CU', 'CV', 'CY', 'CZ',
  'DE', 'DJ', 'DK', 'DM', 'DO', 'DZ',
  'EC', 'EE', 'EG', 'ER', 'ES', 'ET',
  'FI', 'FJ', 'FM', 'FR',
  'GA', 'GB', 'GD', 'GE', 'GH', 'GM', 'GN', 'GQ', 'GR', 'GT', 'GW', 'GY',
  'HN', 'HR', 'HT', 'HU',
  'ID', 'IE', 'IL', 'IN', 'IQ', 'IR', 'IS', 'IT',
  'JM', 'JO', 'JP',
  'KE', 'KG', 'KH', 'KI', 'KM', 'KN', 'KP', 'KR', 'KW', 'KZ',
  'LA', 'LB', 'LC', 'LI', 'LK', 'LR', 'LS', 'LT', 'LU', 'LV', 'LY',
  'MA', 'MC', 'MD', 'ME', 'MG', 'MH', 'MK', 'ML', 'MM', 'MN', 'MR', 'MT', 'MU', 'MV', 'MW', 'MX', 'MY', 'MZ',
  'NA', 'NE', 'NG', 'NI', 'NL', 'NO', 'NP', 'NR', 'NZ',
  'OM',
  'PA', 'PE', 'PG', 'PH', 'PK', 'PL', 'PT', 'PW', 'PY',
  'QA',
  'RO', 'RS', 'RU', 'RW',
  'SA', 'SB', 'SC', 'SD', 'SE', 'SG', 'SI', 'SK', 'SL', 'SM', 'SN', 'SO', 'SR', 'SS', 'ST', 'SV', 'SY', 'SZ',
  'TD', 'TG', 'TH', 'TJ', 'TL', 'TM', 'TN', 'TO', 'TR', 'TT', 'TV', 'TW', 'TZ',
  'UA', 'UG', 'US', 'UY', 'UZ',
  'VA', 'VC', 'VE', 'VN', 'VU',
  'WS',
  'XK',
  'YE',
  'ZA', 'ZM', 'ZW'
]

const { currentLocale } = useLocale()

const countryOptions = computed(() => {
  let displayNames: Intl.DisplayNames | null = null
  try {
    displayNames = new Intl.DisplayNames([currentLocale.value], { type: 'region' })
  } catch {
    displayNames = null
  }
  const collator = new Intl.Collator(currentLocale.value, { sensitivity: 'base' })
  return COUNTRY_CODES.map(code => ({
    value: code,
    label: displayNames?.of(code) ?? code
  })).sort((a, b) => collator.compare(a.label, b.label))
})

function translateCountry(value: string | undefined | null): string {
  if (!value) return ''
  if (value.length === 2 && /^[A-Za-z]{2}$/.test(value)) {
    try {
      return new Intl.DisplayNames([currentLocale.value], { type: 'region' })
        .of(value.toUpperCase()) ?? value
    } catch {
      return value
    }
  }
  return value
}

const currencyOptions = computed(() => {
  let displayNames: Intl.DisplayNames | null = null
  try {
    displayNames = new Intl.DisplayNames([currentLocale.value], { type: 'currency' })
  } catch {
    displayNames = null
  }
  const collator = new Intl.Collator(currentLocale.value, { sensitivity: 'base' })
  return SUPPORTED_CURRENCIES.map(code => ({
    value: code,
    label: displayNames?.of(code) ? `${code} — ${displayNames.of(code)}` : code
  })).sort((a, b) => collator.compare(a.label, b.label))
})

// Full IANA list from the runtime — the previous curated list had no
// Asia/Africa/Oceania zones (reported by a user in GMT+7).
const timezoneOptions = Intl.supportedValuesOf('timeZone').map(tz => ({ label: tz, value: tz }))

const editing = ref(false)
const isSaving = ref(false)
const form = ref({
  name: '',
  tax_id: '',
  legal_name: '',
  street: '',
  city: '',
  postal_code: '',
  country: '',
  phone: '',
  email: '',
  timezone: 'Europe/Madrid',
  currency: 'EUR'
})

function loadForm() {
  const c = clinic.currentClinic.value
  form.value = {
    name: c?.name || '',
    tax_id: c?.tax_id || '',
    legal_name: c?.legal_name || '',
    street: c?.address?.street || '',
    city: c?.address?.city || '',
    postal_code: c?.address?.postal_code || '',
    country: c?.address?.country || '',
    phone: c?.phone || '',
    email: c?.email || '',
    timezone: c?.timezone || 'Europe/Madrid',
    currency: c?.currency || 'EUR'
  }
}

function startEdit() {
  loadForm()
  editing.value = true
}

function cancelEdit() {
  editing.value = false
}

async function save() {
  isSaving.value = true
  const address: ClinicAddress = {
    street: form.value.street || undefined,
    city: form.value.city || undefined,
    postal_code: form.value.postal_code || undefined,
    country: form.value.country || undefined
  }
  const updateData: ClinicUpdate = {
    name: form.value.name || undefined,
    tax_id: form.value.tax_id || undefined,
    legal_name: form.value.legal_name || '',
    address,
    phone: form.value.phone || undefined,
    email: form.value.email || undefined,
    timezone: form.value.timezone || undefined,
    currency: form.value.currency || undefined
  }
  const result = await clinic.updateClinic(updateData)
  isSaving.value = false
  if (result) editing.value = false
}

function formatAddress(address?: Record<string, string>): string {
  if (!address) return '—'
  const parts = []
  if (address.street) parts.push(address.street)
  const cityLine = [address.postal_code, address.city].filter(Boolean).join(' ')
  if (cityLine) parts.push(cityLine)
  if (address.country) parts.push(translateCountry(address.country))
  return parts.length > 0 ? parts.join(', ') : '—'
}
</script>

<template>
  <SectionCard
    icon="i-lucide-building-2"
    :title="t('settings.clinicInfo')"
  >
    <template
      v-if="canEdit && !editing"
      #actions
    >
      <UButton
        icon="i-lucide-pencil"
        size="xs"
        variant="ghost"
        @click="startEdit"
      >
        {{ t('settings.editClinicInfo') }}
      </UButton>
    </template>

    <p class="text-caption text-subtle mb-4">
      {{ t('settings.clinicInfoDescription') }}
    </p>

    <div
      v-if="clinic.isLoading.value"
      class="space-y-3"
    >
      <USkeleton class="h-4 w-24" />
      <USkeleton class="h-4 w-48" />
      <USkeleton class="h-4 w-64" />
    </div>

    <!-- Read view -->
    <div
      v-else-if="!editing && clinic.currentClinic.value"
      class="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-3"
    >
      <DataField
        :label="t('settings.clinicName')"
        :value="clinic.currentClinic.value.name"
      />
      <DataField
        :label="t('settings.taxId')"
        :value="clinic.currentClinic.value.tax_id"
      />
      <DataField
        :label="t('settings.legalName')"
        :value="clinic.currentClinic.value.legal_name"
      />
      <DataField :label="t('settings.street')">
        {{ formatAddress(clinic.currentClinic.value.address) }}
      </DataField>
      <DataField
        :label="t('settings.phone')"
        :value="clinic.currentClinic.value.phone"
      />
      <DataField
        :label="t('common.email')"
        :value="clinic.currentClinic.value.email"
      />
      <DataField
        :label="t('settings.timezone')"
        :value="clinic.currentClinic.value.timezone"
      />
      <DataField
        :label="t('settings.currency')"
        :value="clinic.currentClinic.value.currency"
      />
    </div>

    <!-- Edit view -->
    <form
      v-else-if="editing"
      class="space-y-4"
      @submit.prevent="save"
    >
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <UFormField :label="t('settings.clinicName')">
          <UInput
            v-model="form.name"
            required
          />
        </UFormField>
        <UFormField :label="t('settings.taxId')">
          <UInput v-model="form.tax_id" />
        </UFormField>
      </div>

      <UFormField
        :label="t('settings.legalName')"
        :help="t('settings.legalNameHelp')"
      >
        <UInput v-model="form.legal_name" />
      </UFormField>

      <UFormField :label="t('settings.street')">
        <UInput v-model="form.street" />
      </UFormField>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <UFormField :label="t('settings.postalCode')">
          <UInput v-model="form.postal_code" />
        </UFormField>
        <UFormField :label="t('settings.city')">
          <UInput v-model="form.city" />
        </UFormField>
        <UFormField :label="t('settings.country')">
          <USelectMenu
            v-model="form.country"
            :items="countryOptions"
            value-key="value"
            label-key="label"
            searchable
            :search-input="{ placeholder: t('settings.countrySearchPlaceholder') }"
            :placeholder="t('settings.countryPlaceholder')"
            class="w-full"
          />
        </UFormField>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <UFormField :label="t('settings.phone')">
          <UInput
            v-model="form.phone"
            type="tel"
          />
        </UFormField>
        <UFormField :label="t('common.email')">
          <UInput
            v-model="form.email"
            type="email"
          />
        </UFormField>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <UFormField
          :label="t('settings.timezone')"
          :help="t('settings.timezoneHelp')"
        >
          <USelectMenu
            v-model="form.timezone"
            :items="timezoneOptions"
            value-key="value"
            label-key="label"
            searchable
            class="w-full"
          />
        </UFormField>
        <UFormField
          :label="t('settings.currency')"
          :help="t('settings.currencyHelp')"
        >
          <USelect
            v-model="form.currency"
            :items="currencyOptions"
            value-key="value"
            label-key="label"
          />
        </UFormField>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <UButton
          variant="ghost"
          @click="cancelEdit"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          type="submit"
          :loading="isSaving"
        >
          {{ t('settings.saveChanges') }}
        </UButton>
      </div>
    </form>
  </SectionCard>
</template>
