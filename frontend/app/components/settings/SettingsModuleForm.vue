<script setup lang="ts">
import type { ApiResponse } from '~~/app/types'
import { errorDetail } from '~~/app/utils/error'
import type { ModuleSettings, SettingDeclaration } from '~~/app/utils/settingsForm'
import { initialFormValues, writableValues } from '~~/app/utils/settingsForm'

const props = defineProps<{ module: string }>()

const { t } = useI18n()
const api = useApi()
const toast = useToast()

const data = ref<ModuleSettings | null>(null)
const form = reactive<Record<string, unknown>>({})
const loading = ref(true)
const loadError = ref(false)
const saving = ref(false)

onMounted(load)

async function load() {
  loading.value = true
  loadError.value = false
  try {
    const response = await api.get<ApiResponse<ModuleSettings>>(
      `/api/v1/settings/${props.module}`,
      { errorToast: false }
    )
    data.value = response.data
    Object.assign(form, initialFormValues(response.data))
  } catch (e: unknown) {
    loadError.value = true
    toast.add({
      title: t('common.error'),
      description: errorDetail(e),
      color: 'error'
    })
  } finally {
    loading.value = false
  }
}

function setInteger(key: string, value: string | number) {
  form[key] = value === '' ? null : Number(value)
}

function invalidInteger(setting: SettingDeclaration): boolean {
  return setting.writable
    && setting.type === 'integer'
    && !setting.nullable
    && (form[setting.key] === '' || form[setting.key] === null || form[setting.key] === undefined)
}

async function save() {
  if (!data.value) return
  if (data.value.settings.some(invalidInteger)) return
  const values = writableValues(data.value, form)
  if (!Object.keys(values).length) return
  saving.value = true
  try {
    const response = await api.patch<ApiResponse<ModuleSettings>>(
      `/api/v1/settings/${props.module}`,
      { values },
      { errorToast: false }
    )
    data.value = response.data
    Object.assign(form, initialFormValues(response.data))
    toast.add({ title: t('settings.moduleSettings.saved'), color: 'success' })
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorDetail(e),
      color: 'error'
    })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <UCard>
    <div
      v-if="loading"
      class="space-y-3"
    >
      <USkeleton class="h-10 w-full" />
      <USkeleton class="h-10 w-full" />
    </div>

    <p
      v-else-if="loadError"
      class="text-sm text-(--color-text-muted)"
    >
      {{ t('settings.moduleSettings.loadError') }}
    </p>

    <form
      v-else-if="data && data.settings.length"
      class="space-y-5"
      @submit.prevent="save"
    >
      <UFormField
        v-for="setting in data.settings"
        :key="setting.key"
        :label="t(setting.label_key)"
        :description="setting.description_key ? t(setting.description_key) : undefined"
        :error="invalidInteger(setting) ? t('settings.moduleSettings.invalidInteger') : undefined"
      >
        <USwitch
          v-if="setting.type === 'boolean'"
          :model-value="Boolean(form[setting.key])"
          :disabled="!setting.writable"
          @update:model-value="form[setting.key] = $event"
        />
        <UTextarea
          v-else-if="setting.type === 'string' && setting.multiline"
          :model-value="String(form[setting.key] ?? '')"
          :disabled="!setting.writable"
          :maxlength="setting.max_length ?? undefined"
          autoresize
          class="w-full"
          @update:model-value="form[setting.key] = $event"
        />
        <UInput
          v-else-if="setting.type === 'string'"
          :model-value="String(form[setting.key] ?? '')"
          :disabled="!setting.writable"
          :maxlength="setting.max_length ?? undefined"
          class="w-full"
          @update:model-value="form[setting.key] = $event"
        />
        <UInput
          v-else-if="setting.type === 'integer'"
          :model-value="String(form[setting.key] ?? '')"
          type="number"
          :min="setting.min_value ?? undefined"
          :max="setting.max_value ?? undefined"
          :disabled="!setting.writable"
          class="w-full"
          @update:model-value="setInteger(setting.key, $event)"
        />
        <USelect
          v-else
          :model-value="String(form[setting.key] ?? '')"
          :items="setting.choices"
          :disabled="!setting.writable"
          class="w-full"
          @update:model-value="form[setting.key] = $event"
        />
      </UFormField>

      <div
        v-if="data.settings.some(setting => setting.writable)"
        class="flex justify-end"
      >
        <UButton
          type="submit"
          :loading="saving"
        >
          {{ t('settings.moduleSettings.save') }}
        </UButton>
      </div>
    </form>

    <p
      v-else
      class="text-sm text-(--color-text-muted)"
    >
      {{ t('settings.moduleSettings.empty') }}
    </p>
  </UCard>
</template>
