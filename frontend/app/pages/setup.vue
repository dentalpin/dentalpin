<script setup lang="ts">
import type { CodeLang } from '~/types'
import {
  browserTimezone,
  countryOptions as buildCountryOptions,
  currencyOptions as buildCurrencyOptions,
  timezoneOptions as buildTimezoneOptions,
  guessBrowserCountry
} from '~/utils/countries'
import { isValidSpanishTaxId } from '~/utils/spanishTaxId'
import { APP_NAME } from '~/constants/branding'

definePageMeta({
  layout: 'guest'
})

interface CountryPreset {
  code: string
  currency: string
  timezone: string
  language: string
  vat_preset: string
  tax_id_label: string
  tax_id_pattern: string | null
  tax_id_example: string | null
  suggested_modules: string[]
}

const { t } = useI18n()
const api = useApi()
const auth = useAuth()
const toast = useToast()
const { currentLocale, availableLocales, changeLocale } = useLocale()

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const step = ref<1 | 2>(1)
const isLoading = ref(false)
const errorMessage = ref('')
const showAdvanced = ref(false)

const form = reactive({
  firstName: '',
  lastName: '',
  email: '',
  password: '',
  passwordConfirm: '',
  clinicName: '',
  country: '',
  taxId: '',
  timezone: '',
  currency: ''
})

const errors = reactive<Record<string, string>>({})

// ---- Country presets ------------------------------------------------
const presets = ref<Record<string, CountryPreset>>({})
const fallbackPreset = ref<CountryPreset | null>(null)

const preset = computed<CountryPreset | null>(() =>
  presets.value[form.country] ?? fallbackPreset.value
)
const isKnownCountry = computed(() => !!presets.value[form.country])
const isSpain = computed(() => form.country === 'ES')

const countryOptions = computed(() => buildCountryOptions(currentLocale.value))
const currencyOptions = computed(() => buildCurrencyOptions(currentLocale.value))
const timezoneOptions = buildTimezoneOptions()
const localeOptions = computed(() =>
  availableLocales.value.map(l => ({ label: l.name, value: l.code }))
)

const taxIdLabel = computed(() =>
  preset.value?.tax_id_pattern ? preset.value.tax_id_label : t('setup.taxIdGeneric')
)
const taxIdWarning = computed(() =>
  isSpain.value && form.taxId.trim() && !isValidSpanishTaxId(form.taxId)
    ? t('setup.taxIdLooksInvalid')
    : ''
)

onMounted(async () => {
  try {
    const res = await api.get<{ data: { countries: CountryPreset[], fallback: CountryPreset } }>(
      '/api/v1/auth/setup/presets', { skipAuth: true }
    )
    presets.value = Object.fromEntries(res.data.countries.map(c => [c.code, c]))
    fallbackPreset.value = res.data.fallback
  } catch {
    // Presets are a convenience; the wizard still works with manual tz/currency.
  }
  // Timezone is a stronger hint than `navigator.language` (many browsers
  // default to en-US); fall back to the language region.
  const tz = browserTimezone()
  const byTz = tz ? Object.values(presets.value).find(p => p.timezone === tz)?.code : undefined
  const guessed = byTz ?? guessBrowserCountry()
  if (guessed) applyCountry(guessed)
})

function applyCountry(code: string) {
  form.country = code
  const p = presets.value[code] ?? fallbackPreset.value
  const browserTz = browserTimezone()
  // Prefer the browser zone when the user is in the guessed country
  // (multi-zone countries like US/MX/BR); otherwise the preset's main zone.
  form.timezone = (code === guessBrowserCountry() && browserTz) || p?.timezone || browserTz || 'UTC'
  form.currency = p?.currency || 'EUR'
  showAdvanced.value = !presets.value[code]
}

// ---- Validation ------------------------------------------------------
function validateAccount(): boolean {
  errors.firstName = form.firstName.trim() ? '' : t('setup.firstNameRequired')
  errors.lastName = form.lastName.trim() ? '' : t('setup.lastNameRequired')

  const email = form.email.trim()
  if (!email) errors.email = t('setup.emailRequired')
  else if (!EMAIL_RE.test(email)) errors.email = t('setup.emailInvalid')
  else errors.email = ''

  // Mirror the backend strength check: 8+ chars with a letter and a digit.
  if (!form.password) errors.password = t('setup.passwordRequired')
  else if (form.password.length < 8) errors.password = t('setup.passwordTooShort')
  else if (!/[a-zA-Z]/.test(form.password) || !/\d/.test(form.password)) {
    errors.password = t('setup.passwordWeak')
  } else errors.password = ''

  errors.passwordConfirm = form.password === form.passwordConfirm ? '' : t('setup.passwordMismatch')

  return !errors.firstName && !errors.lastName && !errors.email
    && !errors.password && !errors.passwordConfirm
}

function validateClinic(): boolean {
  errors.clinicName = form.clinicName.trim() ? '' : t('setup.clinicNameRequired')
  errors.country = form.country ? '' : t('setup.countryRequired')
  const taxId = form.taxId.trim()
  if (!taxId) errors.taxId = t('setup.taxIdRequired')
  else if (preset.value?.tax_id_pattern
    && !new RegExp(preset.value.tax_id_pattern).test(taxId.toUpperCase().replace(/[\s\-.]/g, ''))) {
    errors.taxId = t('setup.taxIdFormat', { example: preset.value.tax_id_example ?? '' })
  } else errors.taxId = ''
  errors.timezone = form.timezone ? '' : t('setup.timezoneRequired')
  errors.currency = form.currency ? '' : t('setup.currencyRequired')
  return !errors.clinicName && !errors.country && !errors.taxId && !errors.timezone && !errors.currency
}

function goNext() {
  errorMessage.value = ''
  if (validateAccount()) step.value = 2
}

function goBack() {
  errorMessage.value = ''
  step.value = 1
}

async function onSubmit() {
  errorMessage.value = ''
  if (!validateClinic()) return

  isLoading.value = true
  try {
    await api.post('/api/v1/auth/setup', {
      admin_first_name: form.firstName.trim(),
      admin_last_name: form.lastName.trim(),
      admin_email: form.email.trim(),
      admin_password: form.password,
      clinic_name: form.clinicName.trim(),
      clinic_tax_id: form.taxId.trim(),
      country: form.country,
      timezone: form.timezone,
      currency: form.currency,
      // Patient-facing language: the country's when we know it, else the
      // language the admin picked for the UI.
      language: isKnownCountry.value ? preset.value?.language : currentLocale.value
    }, { skipAuth: true })

    // ponytail: re-login con las credenciales recién creadas en vez de
    // inyectar los tokens a mano — una request barata y reusa fetchUser.
    await auth.login({ email: form.email.trim(), password: form.password })

    toast.add({ title: t('setup.success'), color: 'success' })
    await navigateTo('/')
  } catch (error: unknown) {
    const status = (error as { statusCode?: number }).statusCode
    if (status === 409) {
      errorMessage.value = t('setup.alreadyInitialized')
    } else if (status === 422) {
      errorMessage.value = t('setup.invalidData')
    } else {
      errorMessage.value = t('setup.error')
    }
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="w-full max-w-[480px] p-4 sm:p-6">
    <!-- Brand — official logo on a white plate (kit §6), stacked above
         the title row so it doesn't compete with the locale select for
         horizontal space. -->
    <div class="text-center mb-4">
      <span class="inline-flex items-center justify-center bg-white rounded-token-lg shadow-token-sm px-4 py-3">
        <img
          src="/brand/denplant-logo-original.png"
          :alt="APP_NAME"
          class="w-[180px] max-w-full h-auto object-contain"
        >
      </span>
    </div>
    <div class="flex items-start justify-between gap-3 mb-6">
      <div>
        <h1 class="text-h2 text-default">
          {{ t('setup.title') }}
        </h1>
        <p class="text-caption text-muted">
          {{ t('setup.subtitle') }}
        </p>
      </div>
      <USelect
        :model-value="currentLocale"
        :items="localeOptions"
        value-key="value"
        label-key="label"
        icon="i-lucide-languages"
        size="sm"
        :aria-label="t('settings.language')"
        class="w-32 shrink-0"
        @update:model-value="changeLocale($event as CodeLang)"
      />
    </div>

    <UCard>
      <!-- Step indicator -->
      <ol
        class="flex items-center gap-2 mb-5 text-caption"
        :aria-label="t('setup.stepOf', { current: step, total: 2 })"
      >
        <li
          v-for="(label, idx) in [t('setup.stepAccount'), t('setup.stepClinic')]"
          :key="idx"
          class="flex items-center gap-2 min-w-0"
          :class="idx === 0 ? 'shrink-0' : 'flex-1'"
        >
          <span
            v-if="idx > 0"
            class="h-px flex-1 min-w-4"
            :class="step > idx ? 'bg-(--ui-primary)' : 'bg-(--ui-border)'"
            aria-hidden="true"
          />
          <span
            class="flex items-center justify-center w-6 h-6 rounded-full text-xs font-medium shrink-0"
            :class="step > idx + 1
              ? 'bg-(--ui-primary) text-(--ui-bg)'
              : step === idx + 1
                ? 'ring-2 ring-(--ui-primary) text-default'
                : 'ring-1 ring-(--ui-border) text-subtle'"
            :aria-current="step === idx + 1 ? 'step' : undefined"
          >
            <UIcon
              v-if="step > idx + 1"
              name="i-lucide-check"
              class="w-3.5 h-3.5"
            />
            <template v-else>{{ idx + 1 }}</template>
          </span>
          <span
            class="truncate"
            :class="step === idx + 1 ? 'text-default font-medium' : 'text-subtle hidden sm:inline'"
          >{{ label }}</span>
        </li>
      </ol>

      <div
        v-if="errorMessage"
        class="alert-surface-danger rounded-token-md px-3 py-2 flex items-start gap-2 mb-4"
        role="alert"
      >
        <UIcon
          name="i-lucide-alert-circle"
          class="w-4 h-4 mt-0.5 shrink-0"
          :style="{ color: 'var(--color-danger-accent)' }"
        />
        <span class="text-body">{{ errorMessage }}</span>
      </div>

      <!-- Step 1: admin account -->
      <form
        v-if="step === 1"
        class="space-y-4"
        @submit.prevent="goNext"
      >
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <UFormField
            :label="t('setup.firstName')"
            name="firstName"
            :error="errors.firstName || undefined"
          >
            <UInput
              v-model="form.firstName"
              class="w-full"
              autocomplete="given-name"
              :disabled="isLoading"
            />
          </UFormField>
          <UFormField
            :label="t('setup.lastName')"
            name="lastName"
            :error="errors.lastName || undefined"
          >
            <UInput
              v-model="form.lastName"
              class="w-full"
              autocomplete="family-name"
              :disabled="isLoading"
            />
          </UFormField>
        </div>

        <UFormField
          :label="t('setup.email')"
          name="email"
          :error="errors.email || undefined"
        >
          <UInput
            v-model="form.email"
            type="email"
            class="w-full"
            icon="i-lucide-mail"
            autocomplete="email"
            :disabled="isLoading"
          />
        </UFormField>

        <UFormField
          :label="t('setup.password')"
          name="password"
          :error="errors.password || undefined"
          :help="t('setup.passwordHint')"
        >
          <UInput
            v-model="form.password"
            type="password"
            class="w-full"
            icon="i-lucide-lock"
            autocomplete="new-password"
            :disabled="isLoading"
          />
        </UFormField>

        <UFormField
          :label="t('setup.passwordConfirm')"
          name="passwordConfirm"
          :error="errors.passwordConfirm || undefined"
        >
          <UInput
            v-model="form.passwordConfirm"
            type="password"
            class="w-full"
            icon="i-lucide-lock"
            autocomplete="new-password"
            :disabled="isLoading"
          />
        </UFormField>

        <UButton
          type="submit"
          color="primary"
          variant="soft"
          block
        >
          {{ t('setup.next') }}
        </UButton>
      </form>

      <!-- Step 2: clinic details -->
      <form
        v-else
        class="space-y-4"
        @submit.prevent="onSubmit"
      >
        <UFormField
          :label="t('setup.clinicName')"
          name="clinicName"
          :error="errors.clinicName || undefined"
        >
          <UInput
            v-model="form.clinicName"
            class="w-full"
            icon="i-lucide-building-2"
            autocomplete="organization"
            :disabled="isLoading"
          />
        </UFormField>

        <UFormField
          :label="t('setup.country')"
          name="country"
          :error="errors.country || undefined"
          :help="t('setup.countryHelp')"
        >
          <USelectMenu
            :model-value="form.country"
            :items="countryOptions"
            value-key="value"
            label-key="label"
            searchable
            :search-input="{ placeholder: t('settings.countrySearchPlaceholder') }"
            :placeholder="t('settings.countryPlaceholder')"
            icon="i-lucide-globe"
            class="w-full"
            :disabled="isLoading"
            @update:model-value="applyCountry($event as string)"
          />
        </UFormField>

        <UFormField
          :label="taxIdLabel"
          name="taxId"
          :error="errors.taxId || undefined"
          :help="taxIdWarning || undefined"
          :ui="taxIdWarning ? { help: 'text-(--color-warning-accent)' } : undefined"
        >
          <UInput
            v-model="form.taxId"
            class="w-full"
            icon="i-lucide-hash"
            :placeholder="preset?.tax_id_example ?? undefined"
            :disabled="isLoading"
          />
        </UFormField>

        <!-- Derived settings (editable) -->
        <div class="rounded-token-md border border-(--ui-border) overflow-hidden">
          <button
            type="button"
            class="w-full flex items-center justify-between gap-2 px-3 py-2.5 min-h-11 text-left"
            :aria-expanded="showAdvanced"
            @click="showAdvanced = !showAdvanced"
          >
            <span class="text-body text-default">
              {{ t('setup.derivedSettings') }}
              <span
                v-if="form.timezone && form.currency"
                class="text-caption text-muted ms-1"
              >· {{ form.timezone }} · {{ form.currency }}</span>
            </span>
            <UIcon
              :name="showAdvanced ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
              class="w-4 h-4 text-muted shrink-0"
            />
          </button>
          <div
            v-if="showAdvanced"
            class="grid grid-cols-1 sm:grid-cols-2 gap-4 px-3 pb-3"
          >
            <UFormField
              :label="t('settings.timezone')"
              name="timezone"
              :error="errors.timezone || undefined"
            >
              <USelectMenu
                v-model="form.timezone"
                :items="timezoneOptions"
                value-key="value"
                label-key="label"
                searchable
                class="w-full"
                :disabled="isLoading"
              />
            </UFormField>
            <UFormField
              :label="t('settings.currency')"
              name="currency"
              :error="errors.currency || undefined"
            >
              <USelectMenu
                v-model="form.currency"
                :items="currencyOptions"
                value-key="value"
                label-key="label"
                searchable
                class="w-full"
                :disabled="isLoading"
              />
            </UFormField>
          </div>
        </div>

        <div class="alert-surface-info rounded-token-md px-3 py-2 flex items-start gap-2 text-caption">
          <UIcon
            name="i-lucide-sparkles"
            class="w-4 h-4 mt-0.5 shrink-0"
          />
          <span>
            {{ t('setup.willSeed') }}
            <template v-if="isSpain">
              {{ t('setup.willSuggestVerifactu') }}
            </template>
          </span>
        </div>

        <div class="flex gap-3">
          <UButton
            color="neutral"
            variant="ghost"
            :disabled="isLoading"
            @click="goBack"
          >
            {{ t('setup.back') }}
          </UButton>
          <UButton
            type="submit"
            color="primary"
            variant="soft"
            block
            :loading="isLoading"
            :disabled="isLoading"
          >
            {{ t('setup.submit') }}
          </UButton>
        </div>
      </form>
    </UCard>

    <p class="text-center text-caption text-subtle mt-6">
      &copy; {{ new Date().getFullYear() }} {{ APP_NAME }}
    </p>
  </div>
</template>
