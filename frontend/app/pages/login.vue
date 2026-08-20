<script setup lang="ts">
import { APP_NAME } from '~/constants/branding'

definePageMeta({
  layout: 'guest'
})

const { t } = useI18n()
const auth = useAuth()
const toast = useToast()

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const isLoading = ref(false)
const formState = reactive({
  email: '',
  password: ''
})
const errorMessage = ref('')
const emailError = ref('')
const passwordError = ref('')

function validate(): boolean {
  emailError.value = ''
  passwordError.value = ''

  const email = formState.email.trim()
  if (!email) {
    emailError.value = t('auth.emailRequired')
  } else if (!EMAIL_RE.test(email)) {
    emailError.value = t('auth.emailInvalid')
  }

  if (!formState.password) {
    passwordError.value = t('auth.passwordRequired')
  }

  return !emailError.value && !passwordError.value
}

function mapError(err: unknown): string {
  const e = err as {
    statusCode?: number
    status?: number
    message?: string
    data?: { message?: string }
  }
  const status = e.statusCode ?? e.status

  switch (status) {
    case 400:
    case 401:
      return t('auth.invalidCredentials')
    case 403:
      return t('auth.accountInactive')
    case 422:
      return t('auth.invalidCredentials')
    case 429:
      return t('auth.tooManyAttempts')
  }

  if (!status || status === 0 || (e.message && /network|fetch|failed/i.test(e.message))) {
    return t('auth.networkError')
  }
  if (status >= 500) {
    return t('auth.serverError')
  }
  return t('auth.unknownError')
}

async function onSubmit() {
  errorMessage.value = ''
  if (!validate()) return

  isLoading.value = true
  try {
    await auth.login({
      email: formState.email.trim(),
      password: formState.password
    })

    toast.add({
      title: t('auth.loginSuccess'),
      color: 'success'
    })

    await navigateTo('/')
  } catch (error: unknown) {
    console.error('Login error:', error)
    errorMessage.value = mapError(error)
  } finally {
    isLoading.value = false
  }
}

watch(() => formState.email, () => {
  if (emailError.value) emailError.value = ''
  if (errorMessage.value) errorMessage.value = ''
})
watch(() => formState.password, () => {
  if (passwordError.value) passwordError.value = ''
  if (errorMessage.value) errorMessage.value = ''
})
</script>

<template>
  <div class="w-full max-w-[400px] p-6">
    <!-- Brand -->
    <div class="text-center mb-6">
      <img
        src="/logo-icon.svg"
        :alt="APP_NAME"
        width="56"
        height="56"
        class="mx-auto mb-3"
      >
      <h1 class="text-h1 text-default">
        {{ APP_NAME }}
      </h1>
      <p class="text-caption text-muted mt-1">
        {{ t('app.tagline') }}
      </p>
    </div>

    <UCard>
      <form
        class="space-y-4"
        @submit.prevent="onSubmit"
      >
        <!-- Error message — pastel danger (DESIGN §2.4) -->
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
          <span class="text-body">
            {{ errorMessage }}
          </span>
        </div>

        <UFormField
          :label="t('auth.email')"
          name="email"
          :error="emailError || undefined"
        >
          <UInput
            v-model="formState.email"
            type="email"
            class="w-full"
            :placeholder="t('auth.email')"
            icon="i-lucide-mail"
            autocomplete="email"
            :disabled="isLoading"
          />
        </UFormField>

        <UFormField
          :label="t('auth.password')"
          name="password"
          :error="passwordError || undefined"
        >
          <UInput
            v-model="formState.password"
            type="password"
            class="w-full"
            :placeholder="t('auth.password')"
            icon="i-lucide-lock"
            autocomplete="current-password"
            :disabled="isLoading"
          />
        </UFormField>

        <UButton
          type="submit"
          color="primary"
          variant="soft"
          block
          :loading="isLoading"
          :disabled="isLoading"
        >
          {{ t('auth.loginButton') }}
        </UButton>
      </form>
    </UCard>

    <DemoCredentialsHint />

    <p class="text-center text-caption text-subtle mt-6">
      &copy; {{ new Date().getFullYear() }} {{ APP_NAME }}
    </p>
  </div>
</template>
