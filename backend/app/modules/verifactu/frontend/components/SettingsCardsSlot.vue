<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()

const canRead = computed(() => can(PERMISSIONS.verifactu.settingsRead))
</script>

<template>
  <div
    v-if="canRead"
    class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6"
  >
    <UCard class="hover:shadow-md transition">
      <div class="flex items-start gap-4">
        <UIcon
          name="i-lucide-receipt-text"
          class="text-primary-500 text-3xl"
        />
        <div class="flex-1">
          <h3 class="text-lg font-semibold mb-1">
            {{ t('verifactu.settingsCards.title') }}
          </h3>
          <p class="text-gray-500 text-sm mb-3">
            {{ t('verifactu.settingsCards.description') }}
          </p>
          <UButton
            to="/settings/verifactu"
            size="sm"
            variant="soft"
            icon="i-lucide-arrow-right"
          >
            {{ t('verifactu.settingsCards.open') }}
          </UButton>
        </div>
      </div>
    </UCard>
  </div>
</template>
