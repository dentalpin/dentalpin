<script setup lang="ts">
import type { ClinicAddress, ClinicUpdate } from '~/types'
import { PERMISSIONS } from '~/config/permissions'
import {
  countryOptions as buildCountryOptions,
  currencyOptions as buildCurrencyOptions,
  timezoneOptions as buildTimezoneOptions,
  translateCountry as translateCountryName
} from '~/utils/countries'

const { t } = useI18n()
const clinic = useClinic()
const { can } = usePermissions()
const canEdit = computed(() => can(PERMISSIONS.admin.clinicWrite))

const { currentLocale } = useLocale()

const countryOptions = computed(() => buildCountryOptions(currentLocale.value))
const currencyOptions = computed(() => buildCurrencyOptions(currentLocale.value))
const timezoneOptions = buildTimezoneOptions()
const translateCountry = (value: string | undefined | null) => translateCountryName(currentLocale.value, value)

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

// Guided onboarding lands here to *fill in* the clinic data — mount the
// edit form directly instead of parking the user on the read-only view.
const route = useRoute()
if (route.query.onboarding) {
  let opened = false
  watch(clinic.currentClinic, (c) => {
    if (c && canEdit.value && !opened) {
      opened = true
      startEdit()
    }
  }, { immediate: true })
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
          <USelectMenu
            v-model="form.currency"
            :items="currencyOptions"
            value-key="value"
            label-key="label"
            searchable
            class="w-full"
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
