<script setup lang="ts">
import type { ApiResponse } from '~/types'
import type { MfaMode, MfaPolicy } from '~/composables/useMfa'

const { t, te } = useI18n()
const { request, message } = useMfa()
const api = useApi()
const { isAdmin } = usePermissions()
const { currentClinic } = useClinicState()
const policy = ref<MfaPolicy>()
const modes: MfaMode[] = ['off', 'optional', 'required_all', 'required_roles']
const modeOptions = computed(() => modes.map(value => ({ value, label: t(`mfa.mode.${value}`) })))
const roleNames = ref(['admin', 'dentist', 'hygienist', 'assistant', 'receptionist'])
const roleOptions = computed(() => [...new Set([...roleNames.value, ...(policy.value?.roles ?? [])])]
  .map(value => ({
    value,
    label: te(`settings.roles.${value}`) ? t(`settings.roles.${value}`) : value
  })))
const busy = ref(false)
const error = ref('')
const saved = ref(false)

async function load() {
  saved.value = false
  error.value = ''
  const clinicId = currentClinic.value?.id
  try {
    policy.value = (await request<ApiResponse<MfaPolicy>>('clinic/settings/mfa', 'GET', undefined, clinicId)).data
  } catch (cause) {
    error.value = message(cause)
    return
  }
  try {
    const response = await api.get<ApiResponse<Array<{ name: string }>>>('/api/v1/roles', {
      query: { clinic_id: clinicId },
      errorToast: false
    })
    if (response.data.length) roleNames.value = response.data.map(role => role.name)
  } catch {
    // The system roles are always available.
  }
}
onMounted(load)

async function save() {
  if (!policy.value) return
  busy.value = true
  error.value = ''
  saved.value = false
  try {
    const { mode, roles } = policy.value
    const result = await request<ApiResponse<MfaPolicy>>(
      'clinic/settings/mfa',
      'PUT',
      { mode, roles: mode === 'required_roles' ? roles : [] },
      currentClinic.value?.id
    )
    policy.value = result.data
    saved.value = true
  } catch (cause) {
    error.value = message(cause)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <SectionCard
    icon="i-lucide-shield-check"
    :title="t('mfa.policy')"
  >
    <p class="mb-4 text-sm text-muted">
      {{ t('mfa.policyDescription') }}
    </p>
    <form
      v-if="policy"
      method="post"
      class="space-y-4"
      @submit.prevent="save"
    >
      <UFormField :label="t('mfa.policy')">
        <USelect
          v-model="policy.mode"
          :items="modeOptions"
          :disabled="!isAdmin"
        />
      </UFormField>
      <UFormField
        v-if="policy.mode === 'required_roles'"
        :label="t('mfa.roles')"
      >
        <USelectMenu
          v-model="policy.roles"
          :items="roleOptions"
          value-key="value"
          multiple
          :disabled="!isAdmin"
        />
      </UFormField>
      <UButton
        v-if="isAdmin"
        type="submit"
        :loading="busy"
        :disabled="policy.mode === 'required_roles' && !policy.roles.length"
      >
        {{ t('settings.saveChanges') }}
      </UButton>
      <p
        v-if="saved"
        role="status"
        class="text-sm text-success"
      >
        {{ t('mfa.policySaved') }}
      </p>
    </form>
    <p
      v-if="error"
      role="alert"
      class="mt-3 text-sm text-error"
    >
      {{ error }}
    </p>
  </SectionCard>
</template>
