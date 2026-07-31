<script setup lang="ts">
// Toolbar slot for the invoice list. Multi-select severity filter +
// one-click "Solo problemas" chip that preselects warning + error.
// Talks to billing via the generic onChange callback in ctx — billing
// stores the value and re-fetches.

interface FilterCtx {
  severity: string[]
  onChange: (next: string[]) => void
  clinic?: { country?: string | null } | null
}

const props = defineProps<{ ctx: FilterCtx }>()
const { t } = useI18n()

type Severity = 'ok' | 'warning' | 'pending' | 'error'

interface Option {
  value: Severity
  label: string
  icon: string
}

const options = computed<Option[]>(() => [
  { value: 'ok', label: t('verifactu.filter.options.ok'), icon: 'i-lucide-check' },
  { value: 'warning', label: t('verifactu.filter.options.warning'), icon: 'i-lucide-alert-triangle' },
  { value: 'pending', label: t('verifactu.filter.options.pending'), icon: 'i-lucide-clock-3' },
  { value: 'error', label: t('verifactu.filter.options.error'), icon: 'i-lucide-x' }
])

const selected = computed<Severity[]>({
  get: () => (props.ctx.severity ?? []) as Severity[],
  set: next => props.ctx.onChange(next)
})

const PROBLEM_SET: Severity[] = ['error', 'warning']
const onlyProblems = computed(() =>
  PROBLEM_SET.every(s => selected.value.includes(s))
  && selected.value.every(s => PROBLEM_SET.includes(s))
)

function toggleOnlyProblems() {
  if (onlyProblems.value) {
    props.ctx.onChange([])
  } else {
    props.ctx.onChange([...PROBLEM_SET])
  }
}

const filterLabel = computed(() => {
  const n = selected.value.length
  return n > 0
    ? `${t('verifactu.filter.label')} (${n})`
    : t('verifactu.filter.label')
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-2">
    <USelectMenu
      v-model="selected"
      :items="options"
      value-key="value"
      multiple
      :placeholder="filterLabel"
      class="w-56"
    >
      <template #default="{ open }">
        <UButton
          icon="i-lucide-shield-check"
          variant="outline"
          color="neutral"
          size="sm"
          :class="{ 'ring-1 ring-primary': selected.length > 0 }"
        >
          {{ filterLabel }}
          <UIcon
            :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
            class="ml-1"
          />
        </UButton>
      </template>
      <template #item="{ item }">
        <div class="flex items-center gap-2">
          <UIcon :name="(item as Option).icon" />
          <span>{{ (item as Option).label }}</span>
        </div>
      </template>
    </USelectMenu>
    <UButton
      :variant="onlyProblems ? 'solid' : 'soft'"
      :color="onlyProblems ? 'error' : 'neutral'"
      size="sm"
      icon="i-lucide-alert-octagon"
      @click="toggleOnlyProblems"
    >
      {{ t('verifactu.filter.shortcut') }}
    </UButton>
  </div>
</template>
