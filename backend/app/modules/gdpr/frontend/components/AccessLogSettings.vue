<script setup lang="ts">
import type { ApiResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import AccessLog from './AccessLog.vue'

type Staff = { id: string, name: string | null }
const api = useApi()
const { can } = usePermissions()
const { t } = useI18n()
const selected = ref<string>()
const years = ref<number>()
const retentionStatus = ref<'saved' | 'error'>()
const saving = ref(false)
const { data, status } = await useAsyncData('gdpr:access-log:users', () =>
  api.get<ApiResponse<Staff[]>>('/api/v1/gdpr/access-log/users', { errorToast: false })
)
const people = computed(() => (data.value?.data ?? []).map(person => ({
  value: person.id,
  label: person.name || person.id
})))

const { data: retention } = await useAsyncData('gdpr:access-log:retention', () =>
  api.get<ApiResponse<{ years: number }>>('/api/v1/gdpr/access-log/retention', { errorToast: false })
)
watchEffect(() => {
  years.value = retention.value?.data.years
})

const validRetention = computed(() => years.value !== undefined
  && Number.isInteger(years.value)
  && years.value >= 1
  && years.value <= 30)

async function saveRetention() {
  if (!validRetention.value || saving.value) return
  saving.value = true
  retentionStatus.value = undefined
  try {
    retention.value = await api.put<ApiResponse<{ years: number }>>(
      '/api/v1/gdpr/access-log/retention', { years: years.value }, { errorToast: false }
    )
    retentionStatus.value = 'saved'
  } catch {
    retentionStatus.value = 'error'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-6">
    <UCard>
      <template #header>
        <h2 class="font-semibold">
          {{ t('gdprAccess.byUser') }}
        </h2>
      </template>
      <div class="space-y-4">
        <p
          v-if="status === 'error'"
          role="alert"
          class="text-sm text-error"
        >
          {{ t('gdprAccess.loadError') }}
        </p>
        <UFormField
          v-else
          :label="t('gdprAccess.staff')"
        >
          <USelectMenu
            v-model="selected"
            :items="people"
            value-key="value"
            :loading="status === 'pending'"
            :placeholder="t('gdprAccess.chooseStaff')"
            class="w-full sm:w-72"
          />
        </UFormField>
        <AccessLog
          v-if="selected"
          :user-id="selected"
        />
      </div>
    </UCard>
    <UCard v-if="retention">
      <template #header>
        <h2 class="font-semibold">
          {{ t('gdprAccess.retention') }}
        </h2>
      </template>
      <form
        class="flex flex-wrap items-end gap-3"
        @submit.prevent="saveRetention"
      >
        <UFormField :label="t('gdprAccess.retentionYears')">
          <UInput
            v-model.number="years"
            type="number"
            :min="1"
            :max="30"
            :disabled="!can(PERMISSIONS.gdpr.retentionWrite)"
          />
        </UFormField>
        <UButton
          v-if="can(PERMISSIONS.gdpr.retentionWrite)"
          type="submit"
          :disabled="!validRetention"
          :loading="saving"
        >
          {{ t('gdprAccess.save') }}
        </UButton>
      </form>
      <p
        v-if="retentionStatus"
        role="status"
        class="mt-2 text-sm"
        :class="retentionStatus === 'error' ? 'text-error' : 'text-muted'"
      >
        {{ t(retentionStatus === 'error' ? 'gdprAccess.saveError' : 'gdprAccess.saved') }}
      </p>
    </UCard>
  </div>
</template>
