<script setup lang="ts">
import SignatureCanvas from '~~/app/components/shared/SignatureCanvas.vue'

definePageMeta({ layout: 'public' })
useHead({ meta: [{ name: 'referrer', content: 'no-referrer' }] })
const { t, locale, loadLocaleMessages } = useI18n()
const config = useRuntimeConfig()
const token = ref('')
const endpoint = `${config.public.apiBaseUrl}/api/v1/documents/public/consents/current`
interface PublicConsent { title: string, text: string, patient: string, clinic: string, purpose: string, locale?: string }
const item = ref<PublicConsent | null>(null)
const signer = ref('')
const relation = ref('patient')
const relationOptions = computed(() => [
  { label: t('documents.consent.patient'), value: 'patient' },
  { label: t('documents.consent.guardian'), value: 'guardian' },
  { label: t('documents.consent.representative'), value: 'representative' }
])
const signature = ref<string | null>(null)
const canvas = ref<InstanceType<typeof SignatureCanvas> | null>(null)
watch(relation, (value) => {
  signer.value = value === 'patient' ? item.value?.patient || '' : ''
})
const busy = ref(false)
const error = ref(false)
const submitFailed = ref(false)
const done = ref(false)
let loadGeneration = 0
// In memory only, like /p/budget: setLocale would persist the cookie and
// overwrite the tablet's own language for the next visitor (#235).
async function applyLinkLanguage(lang?: string) {
  if (!lang || lang === locale.value) return
  try {
    await loadLocaleMessages(lang as never)
    locale.value = lang as never
  } catch {
    // keep the current locale
  }
}
async function loadConsent() {
  const generation = ++loadGeneration
  token.value = window.location.hash.slice(1)
  item.value = null
  signer.value = ''
  relation.value = 'patient'
  signature.value = null
  error.value = false
  submitFailed.value = false
  done.value = false
  if (!token.value) {
    error.value = true
    return
  }
  try {
    const result = await $fetch<{ data: PublicConsent }>(endpoint, { credentials: 'omit', headers: { Authorization: `Bearer ${token.value}` } })
    if (generation !== loadGeneration) return
    await applyLinkLanguage(result.data?.locale)
    if (generation !== loadGeneration) return
    item.value = result.data
    signer.value = result.data?.patient || ''
  } catch {
    if (generation === loadGeneration) error.value = true
  }
}
function onHashChange() {
  if (window.location.hash.slice(1) !== token.value) void loadConsent()
}
onMounted(() => {
  window.addEventListener('hashchange', onHashChange)
  void loadConsent()
})
onUnmounted(() => {
  loadGeneration++
  window.removeEventListener('hashchange', onHashChange)
})

async function submit() {
  if (!signature.value || !signer.value.trim()) return
  const generation = loadGeneration
  busy.value = true
  submitFailed.value = false
  try {
    await $fetch(`${endpoint}/sign`, { method: 'POST', credentials: 'omit', headers: { Authorization: `Bearer ${token.value}` }, body: {
      signer_name: signer.value, relationship_to_patient: relation.value, signature: signature.value
    } })
    if (generation === loadGeneration) {
      done.value = true
      item.value = null
    }
  } catch (e: unknown) {
    if (generation !== loadGeneration) return
    // Only these two mean the link is spent; anything else keeps the signature (#1042).
    const status = (e as { statusCode?: number }).statusCode
    if (status === 404 || status === 409) error.value = true
    else submitFailed.value = true
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="mx-auto max-w-3xl px-6 py-8 space-y-6">
    <p
      v-if="done"
      role="status"
    >
      {{ t('documents.consent.completed') }}
    </p>
    <p
      v-else-if="error"
      role="alert"
    >
      {{ t('documents.consent.linkError') }}
    </p>
    <template v-else-if="item">
      <header>
        <p>{{ item.clinic }}</p><h1 class="text-2xl font-semibold">
          {{ item.title }}
        </h1><p>{{ item.patient }}</p>
      </header>
      <p
        v-if="item.purpose === 'revoke'"
        class="font-semibold"
      >
        {{ t('documents.consent.revocationNotice') }}
      </p>
      <div class="whitespace-pre-wrap rounded border p-5">
        {{ item.text }}
      </div>
      <UFormField
        :label="t('documents.consent.signer')"
        name="signer"
      >
        <UInput
          v-model="signer"
          class="w-full"
          size="lg"
        />
      </UFormField>
      <UFormField
        :label="t('documents.consent.relationship')"
        name="relationship"
      >
        <USelect
          v-model="relation"
          :items="relationOptions"
          class="w-full"
          size="lg"
        />
      </UFormField>
      <div>
        <p>{{ t('documents.consent.drawSignature') }}</p><SignatureCanvas
          ref="canvas"
          v-model="signature"
        />
        <UButton
          variant="ghost"
          @click="canvas?.clear()"
        >
          {{ t('documents.consent.clear') }}
        </UButton>
      </div>
      <p
        v-if="submitFailed"
        role="alert"
      >
        {{ t('documents.consent.submitFailed') }}
      </p>
      <UButton
        :disabled="busy || !signature || !signer.trim()"
        size="lg"
        @click="submit"
      >
        {{ t('documents.consent.confirm') }}
      </UButton>
    </template>
    <p v-else>
      {{ t('documents.consent.loading') }}
    </p>
  </main>
</template>
