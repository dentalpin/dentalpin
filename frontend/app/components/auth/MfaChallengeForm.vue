<script setup lang="ts">
import type { MfaChallenge } from '~/composables/useMfa'

const props = defineProps<{
  challenge: MfaChallenge
  selfEnrollment?: boolean
}>()
const emit = defineEmits<{ verified: [], cancel: [] }>()
const { t } = useI18n()
const { request, message } = useMfa()
const code = ref('')
const error = ref('')
const busy = ref(false)
const recovery = ref<string[]>([])

async function verify() {
  busy.value = true
  error.value = ''
  try {
    const path = props.selfEnrollment ? 'mfa/totp/confirm' : 'mfa/verify'
    const result = await request<{ recovery_codes: string[] | null }>(
      path, 'POST', { code: code.value, mfa_token: props.challenge.mfa_token }
    )
    code.value = ''
    if (result.recovery_codes?.length) recovery.value = result.recovery_codes
    else emit('verified')
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}

function done() {
  recovery.value = []
  emit('verified')
}
</script>

<template>
  <div
    v-if="recovery.length"
    class="space-y-4"
  >
    <h2 class="text-lg font-semibold">
      {{ t('mfa.recoveryTitle') }}
    </h2>
    <p class="text-sm text-muted">
      {{ t('mfa.saveRecovery') }}
    </p>
    <ul class="grid grid-cols-1 gap-2 rounded-md bg-elevated p-3 font-mono text-sm sm:grid-cols-2">
      <li
        v-for="entry in recovery"
        :key="entry"
      >
        {{ entry }}
      </li>
    </ul>
    <UButton
      type="button"
      block
      @click="done"
    >
      {{ t('mfa.savedRecovery') }}
    </UButton>
  </div>

  <form
    v-else
    method="post"
    class="space-y-4"
    @submit.prevent="verify"
  >
    <h2 class="text-lg font-semibold">
      {{ t(challenge.mode === 'enroll' ? 'mfa.enroll' : 'mfa.verify') }}
    </h2>
    <template v-if="challenge.mode === 'enroll'">
      <p class="text-sm text-muted">
        {{ t('mfa.scan') }}
      </p>
      <img
        v-if="challenge.qr_code"
        :src="challenge.qr_code"
        :alt="t('mfa.qrAlt')"
        width="180"
        height="180"
        class="rounded-md"
      >
      <UFormField :label="t('mfa.manualKey')">
        <UInput
          :model-value="challenge.secret ?? ''"
          class="w-full font-mono"
          readonly
        />
      </UFormField>
    </template>
    <UFormField :label="t(challenge.mode === 'enroll' ? 'mfa.code' : 'mfa.codeOrRecovery')">
      <UInput
        v-model="code"
        autocomplete="one-time-code"
        :inputmode="challenge.mode === 'enroll' ? 'numeric' : 'text'"
        :maxlength="challenge.mode === 'enroll' ? 6 : 64"
        class="w-full"
        required
      />
    </UFormField>
    <p
      v-if="error"
      role="alert"
      class="text-sm text-error"
    >
      {{ error }}
    </p>
    <div class="flex gap-3">
      <UButton
        type="button"
        color="neutral"
        variant="ghost"
        :disabled="busy"
        @click="emit('cancel')"
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
</template>
