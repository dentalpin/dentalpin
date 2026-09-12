<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()

const canRead = computed(() => can(PERMISSIONS.razorpay.settingsRead))
</script>

<template>
  <div
    v-if="canRead"
    class="grid grid-cols-1 md:grid-cols-2 gap-4"
  >
    <SettingsSection
      icon="i-lucide-credit-card"
      :title="t('razorpay.settingsCards.title')"
      :subtitle="t('razorpay.settingsCards.description')"
      to="/settings/razorpay"
    />
  </div>
</template>
