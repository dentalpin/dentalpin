<script setup lang="ts">
/**
 * Invite landing: consume the one-time token from the URL, set a password
 * and sign in. Public route (guest layout).
 */
definePageMeta({
  layout: 'guest'
})

const { t } = useI18n()
const route = useRoute()
const api = useApi()
const auth = useAuth()
const toast = useToast()

const token = computed(() => (typeof route.query.token === 'string' ? route.query.token : ''))
const password = ref('')
const passwordConfirm = ref('')
const errors = reactive<Record<string, string>>({})
const errorMessage = ref('')
const isLoading = ref(false)

function validate(): boolean {
  if (!password.value) errors.password = t('setup.passwordRequired')
  else if (password.value.length < 12) errors.password = t('setup.passwordTooShort')
  else if (!/[a-zA-Z]/.test(password.value) || !/\d/.test(password.value)) errors.password = t('setup.passwordWeak')
  else errors.password = ''
  errors.passwordConfirm = password.value === passwordConfirm.value ? '' : t('setup.passwordMismatch')
  return !errors.password && !errors.passwordConfirm
}

async function onSubmit() {
  errorMessage.value = ''
  if (!validate()) return
  isLoading.value = true
  try {
    const res = await api.post<{ access_token: string, refresh_token: string }>(
      '/api/v1/auth/set-password',
      { token: token.value, password: password.value },
      // The catch renders errorMessage inline on the form.
      { skipAuth: true, errorToast: false }
    )
    await auth.applyTokens(res.access_token, res.refresh_token)
    toast.add({ title: t('setup.success'), color: 'success' })
    await navigateTo('/')
  } catch (error: unknown) {
    const status = (error as { statusCode?: number }).statusCode
    errorMessage.value = status === 400 ? t('settings.invite.invalidToken') : t('setup.error')
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="w-full max-w-[440px] p-4 sm:p-6">
    <div class="text-center mb-6">
      <img
        src="/logo-icon.svg"
        alt="DentalPin"
        width="56"
        height="56"
        class="mx-auto mb-3"
      >
      <h1 class="text-h1 text-default">
        {{ t('settings.invite.setPasswordTitle') }}
      </h1>
      <p class="text-caption text-muted mt-1">
        {{ t('settings.invite.setPasswordSubtitle') }}
      </p>
    </div>

    <UCard>
      <div
        v-if="!token"
        class="alert-surface-danger rounded-token-md px-3 py-2 text-body"
        role="alert"
      >
        {{ t('settings.invite.invalidToken') }}
      </div>

      <form
        v-else
        class="space-y-4"
        @submit.prevent="onSubmit"
      >
        <div
          v-if="errorMessage"
          class="alert-surface-danger rounded-token-md px-3 py-2 flex items-start gap-2"
          role="alert"
        >
          <UIcon
            name="i-lucide-alert-circle"
            class="w-4 h-4 mt-0.5 shrink-0"
            :style="{ color: 'var(--color-danger-accent)' }"
          />
          <span class="text-body">{{ errorMessage }}</span>
        </div>

        <UFormField
          :label="t('setup.password')"
          name="password"
          :error="errors.password || undefined"
          :help="t('setup.passwordHint')"
        >
          <UInput
            v-model="password"
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
            v-model="passwordConfirm"
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
          block
          :loading="isLoading"
          :disabled="isLoading"
        >
          {{ t('settings.invite.setPasswordSubmit') }}
        </UButton>
      </form>
    </UCard>
  </div>
</template>
