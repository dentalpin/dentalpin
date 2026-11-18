<script setup lang="ts">
import type { ApiResponse } from '~/types'
import type { MfaChallenge, MfaProfile } from '~/composables/useMfa'

const { t } = useI18n()
const auth = useAuth()
const { request, message } = useMfa()
const state = ref<MfaProfile>()
const challenge = ref<MfaChallenge>()
const password = ref('')
const code = ref('')
const editing = ref(false)
const busy = ref(false)
const error = ref('')

async function load() {
  try {
    state.value = (await request<ApiResponse<MfaProfile>>('mfa/status', 'GET')).data
  } catch (cause) {
    error.value = message(cause)
  }
}

onMounted(load)

function cancel() {
  challenge.value = undefined
  editing.value = false
  password.value = ''
  code.value = ''
  error.value = ''
}

async function verified() {
  cancel()
  await auth.fetchUser()
  await load()
}

async function submit() {
  busy.value = true
  error.value = ''
  try {
    if (state.value?.enabled) {
      await request('mfa/disable', 'POST', { password: password.value, code: code.value })
      await verified()
    } else {
      challenge.value = await request<MfaChallenge>('mfa/totp/enroll', 'POST', { password: password.value })
      editing.value = false
    }
  } catch (cause) {
    error.value = message(cause)
  } finally {
    password.value = ''
    code.value = ''
    busy.value = false
  }
}
</script>

<template>
  <SectionCard
    icon="i-lucide-shield-check"
    :title="t('mfa.title')"
  >
    <MfaChallengeForm
      v-if="challenge"
      :challenge="challenge"
      self-enrollment
      @verified="verified"
      @cancel="cancel"
    />
    <form
      v-else-if="editing"
      method="post"
      class="space-y-4"
      @submit.prevent="submit"
    >
      <UFormField :label="t('setup.password')">
        <UInput
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </UFormField>
      <UFormField
        v-if="state?.enabled"
        :label="t('mfa.codeOrRecovery')"
      >
        <UInput
          v-model="code"
          autocomplete="one-time-code"
          required
        />
      </UFormField>
      <div class="flex gap-2">
        <UButton
          type="button"
          color="neutral"
          variant="ghost"
          @click="cancel"
        >
          {{ t('common.cancel') }}
        </UButton>
        <UButton
          type="submit"
          :loading="busy"
        >
          {{ t('mfa.confirm') }}
        </UButton>
      </div>
    </form>
    <template v-else-if="state">
      <p class="mb-3 text-sm text-muted">
        {{ t(state.enabled ? (state.required ? 'mfa.required' : 'mfa.enabled') : 'mfa.notEnabled') }}
      </p>
      <UButton
        v-if="state.enabled ? !state.required : state.allowed"
        @click="editing = true"
      >
        {{ t(state.enabled ? 'mfa.disable' : 'mfa.enroll') }}
      </UButton>
      <p
        v-else-if="!state.enabled"
        class="text-sm text-muted"
      >
        {{ t('mfa.offByPolicy') }}
      </p>
    </template>
    <p
      v-if="error"
      role="alert"
      class="mt-3 text-sm text-error"
    >
      {{ error }}
    </p>
  </SectionCard>
</template>
