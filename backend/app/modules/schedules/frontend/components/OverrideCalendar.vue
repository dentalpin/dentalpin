<script setup lang="ts" generic="T extends { id: string, start_date: string, end_date: string, kind: string, reason: string | null }">
defineProps<{
  overrides: T[]
  canWrite: boolean
  kindLabels: Record<string, string>
}>()

const emit = defineEmits<{
  add: []
  edit: [override: T]
  delete: [override: T]
}>()

const { t } = useI18n()
</script>

<template>
  <div>
    <div class="flex items-center justify-between mb-3">
      <h3 class="text-base font-semibold">
        {{ t('schedules.clinicHours.overrides') }}
      </h3>
      <UButton
        v-if="canWrite"
        size="sm"
        icon="i-lucide-plus"
        @click="emit('add')"
      >
        {{ t('schedules.overrides.add') }}
      </UButton>
    </div>

    <div
      v-if="overrides.length === 0"
      class="text-sm text-gray-400 italic text-center py-6 border border-dashed rounded-lg"
    >
      {{ t('schedules.overrides.noOverrides') }}
    </div>

    <div
      v-else
      class="space-y-2"
    >
      <div
        v-for="o in overrides"
        :key="o.id"
        class="flex items-center gap-3 p-3 rounded-lg border border-gray-200 dark:border-gray-800"
      >
        <UBadge
          :color="o.kind === 'closed' || o.kind === 'unavailable' ? 'error' : 'warning'"
          variant="subtle"
        >
          {{ kindLabels[o.kind] ?? o.kind }}
        </UBadge>
        <div class="flex-1 min-w-0">
          <div class="font-medium truncate">
            {{ o.reason || '—' }}
          </div>
          <div class="text-sm text-gray-500">
            {{ o.start_date }} → {{ o.end_date }}
          </div>
        </div>
        <UButton
          v-if="canWrite"
          size="xs"
          variant="ghost"
          icon="i-lucide-pencil"
          @click="emit('edit', o)"
        />
        <UButton
          v-if="canWrite"
          size="xs"
          variant="ghost"
          color="error"
          icon="i-lucide-trash-2"
          @click="emit('delete', o)"
        />
      </div>
    </div>
  </div>
</template>
