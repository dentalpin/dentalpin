<script setup lang="ts">
import SignatureCanvas from '~~/app/components/shared/SignatureCanvas.vue'

definePageMeta({ layout: 'public' })
useHead({ meta: [{ name: 'referrer', content: 'no-referrer' }] })
const { t } = useI18n()
const config = useRuntimeConfig()
const token = ref('')
const endpoint = `${config.public.apiBaseUrl}/api/v1/documents/public/consents/current`
interface PublicConsent { title: string, text: string, patient: string, clinic: string, purpose: string }
const item = ref<PublicConsent | null>(null)
const signer = ref('')
const relation = ref('patient')
const signature = ref<string | null>(null)
const canvas = ref<InstanceType<typeof SignatureCanvas> | null>(null)
watch(relation, (value) => {
  signer.value = value === 'patient' ? item.value?.patient || '' : ''
})
const busy = ref(false)
const error = ref(false)
const done = ref(false)
let loadGeneration = 0
async function loadConsent() {
  const generation = ++loadGeneration
  token.value = window.location.hash.slice(1)
  item.value = null
  signer.value = ''
  relation.value = 'patient'
  signature.value = null
  error.value = false
  done.value = false
  if (!token.value) {
    error.value = true
    return
  }
  try {
    const result = await $fetch<{ data: PublicConsent }>(endpoint, { credentials: 'omit', headers: { Authorization: `Bearer ${token.value}` } })
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
  try {
    await $fetch(`${endpoint}/sign`, { method: 'POST', credentials: 'omit', headers: { Authorization: `Bearer ${token.value}` }, body: {
      signer_name: signer.value, relationship_to_patient: relation.value, signature: signature.value
    } })
    if (generation === loadGeneration) {
      done.value = true
      item.value = null
    }
  } catch {
    if (generation === loadGeneration) error.value = true
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
      <label class="block">{{ t('documents.consent.signer') }}<input
        v-model="signer"
        class="mt-1 block w-full rounded border p-3"
      ></label>
      <label class="block">{{ t('documents.consent.relationship') }}
        <select
          v-model="relation"
          class="mt-1 block w-full rounded border p-3"
        >
          <option value="patient">{{ t('documents.consent.patient') }}</option>
          <option value="guardian">{{ t('documents.consent.guardian') }}</option>
          <option value="representative">{{ t('documents.consent.representative') }}</option>
        </select>
      </label>
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
