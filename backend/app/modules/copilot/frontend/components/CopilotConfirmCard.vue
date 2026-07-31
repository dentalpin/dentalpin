<script setup lang="ts">
// Humanized confirmation for a pending write tool: labeled rows with ids
// resolved to names and ISO datetimes formatted, instead of raw JSON.
const props = defineProps<{
  callId: string
  name: string
  args: Record<string, unknown>
  resolved?: 'confirm' | 'reject'
}>()
const emit = defineEmits<{ confirm: [callId: string, decision: 'confirm' | 'reject'] }>()

const { t, te } = useI18n()
const { nameCache } = useCopilot()
const { dateTime } = useCopilotFormat()

const short = computed(() => props.name.split('.').pop() ?? props.name)

const isDestructive = computed(() => /cancel|delete|refund|void|remove/i.test(short.value))

const actionText = computed(() => {
  const key = `copilot.confirm.action.${short.value}`
  return te(key) ? t(key) : t('copilot.confirm.body', { name: short.value })
})

function fieldLabel(key: string): string {
  const k = `copilot.confirm.field.${key}`
  return te(k) ? t(k) : key.replace(/_/g, ' ')
}

function humanize(key: string, value: unknown): string {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'string') {
    if (key.endsWith('_id') || key === 'patient' || key === 'professional') {
      return nameCache.value[value] ?? value
    }
    if (/^\d{4}-\d\d-\d\dT/.test(value)) return dateTime(value)
    return value
  }
  if (typeof value === 'number' && key === 'duration_minutes') return `${value} min`
  if (typeof value === 'boolean') return value ? '✓' : '✗'
  return String(value)
}

const rows = computed(() =>
  Object.entries(props.args)
    .filter(([, v]) => v !== null && v !== undefined && typeof v !== 'object')
    .map(([k, v]) => ({ key: k, label: fieldLabel(k), value: humanize(k, v) }))
)
</script>

<template>
  <UCard
    :ui="{ body: 'p-3 sm:p-3' }"
    :class="isDestructive ? 'ring-2 ring-error' : ''"
  >
    <p class="flex items-center gap-1.5 text-sm font-medium">
      <UIcon
        :name="isDestructive ? 'i-lucide-alert-triangle' : 'i-lucide-shield-question'"
        :class="isDestructive ? 'text-error' : 'text-warning'"
      />
      {{ t('copilot.confirm.title') }}
    </p>
    <p class="mt-1 text-sm text-muted">
      {{ actionText }}
    </p>

    <dl class="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 rounded bg-elevated p-2 text-xs">
      <template
        v-for="row in rows"
        :key="row.key"
      >
        <dt class="capitalize text-muted">
          {{ row.label }}
        </dt>
        <dd class="text-right font-medium">
          {{ row.value }}
        </dd>
      </template>
    </dl>

    <p
      v-if="isDestructive && !resolved"
      class="mt-2 text-xs font-medium text-error"
    >
      {{ t('copilot.confirm.destructiveNote') }}
    </p>

    <div
      v-if="!resolved"
      class="mt-3 flex justify-end gap-2"
    >
      <UButton
        color="neutral"
        variant="ghost"
        size="sm"
        @click="emit('confirm', callId, 'reject')"
      >
        {{ t('copilot.confirm.reject') }}
      </UButton>
      <UButton
        :color="isDestructive ? 'error' : 'primary'"
        size="sm"
        @click="emit('confirm', callId, 'confirm')"
      >
        {{ t('copilot.confirm.approve') }}
      </UButton>
    </div>
    <p
      v-else
      class="mt-2 text-xs text-muted"
    >
      {{ resolved === 'confirm' ? t('copilot.confirm.approved') : t('copilot.confirm.rejected') }}
    </p>
  </UCard>
</template>
