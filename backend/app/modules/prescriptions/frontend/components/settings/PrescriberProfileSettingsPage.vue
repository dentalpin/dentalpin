<script setup lang="ts">
/**
 * Prescriber identity (Settings → Clinical). Own license number used
 * for the snapshot taken at issue time; per-user defaults.
 */
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { getPrescriberProfile, upsertPrescriberProfile } = usePrescriptions()

const canWrite = computed(() => can(PERMISSIONS.prescriptions.write))
const licenseNumber = ref('')
const isLoading = ref(false)

async function refresh() {
  isLoading.value = true
  try {
    const profile = await getPrescriberProfile()
    licenseNumber.value = profile?.license_number || ''
  } finally {
    isLoading.value = false
  }
}

async function save() {
  try {
    await upsertPrescriberProfile(licenseNumber.value.trim() || null)
    toast.add({ title: t('common.success'), color: 'success' })
    await refresh()
  } catch { /* useApi already toasted the failure */ }
}

onMounted(refresh)
</script>

<template>
  <div class="space-y-2">
    <USkeleton
      v-if="isLoading"
      class="h-10"
    />
    <template v-else>
      <UFormField :label="t('prescriptions.licenseLabel')">
        <UInput
          v-model="licenseNumber"
          :disabled="!canWrite"
        />
      </UFormField>
      <UButton
        v-if="canWrite"
        size="xs"
        @click="save"
      >
        {{ t('prescriptions.save') }}
      </UButton>
    </template>
  </div>
</template>
