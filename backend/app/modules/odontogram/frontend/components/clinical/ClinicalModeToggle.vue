<script setup lang="ts">
/**
 * ClinicalModeToggle — compact, responsive navigation for the patient
 * clinical workspace. Every mode remains one tap away on touch screens
 * and arrow-key accessible on desktop.
 */
import type { ClinicalMode } from '~~/app/types'

interface ModeBadges {
  diagnosis?: string | number
  plans?: string | number
  appointments?: string | number
  history?: string | number
}

const props = defineProps<{
  modelValue: ClinicalMode
  badges?: ModeBadges
}>()

const emit = defineEmits<{
  'update:modelValue': [mode: ClinicalMode]
}>()

const { t } = useI18n()
const tablist = ref<HTMLElement | null>(null)

const options = computed(() => [
  {
    value: 'diagnosis',
    label: t('clinical.modes.diagnosis'),
    icon: 'i-lucide-stethoscope',
    badge: props.badges?.diagnosis
  },
  {
    value: 'plans',
    label: t('clinical.modes.plans'),
    icon: 'i-lucide-clipboard-list',
    badge: props.badges?.plans
  },
  {
    value: 'appointments',
    label: t('clinical.modes.appointments'),
    icon: 'i-lucide-calendar',
    badge: props.badges?.appointments
  },
  {
    value: 'history',
    label: t('clinical.modes.history'),
    icon: 'i-lucide-history',
    badge: props.badges?.history
  }
])

function handleKeydown(event: KeyboardEvent, index: number) {
  let nextIndex = index

  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    nextIndex = (index + 1) % options.value.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    nextIndex = (index - 1 + options.value.length) % options.value.length
  } else if (event.key === 'Home') {
    nextIndex = 0
  } else if (event.key === 'End') {
    nextIndex = options.value.length - 1
  } else {
    return
  }

  event.preventDefault()
  const nextOption = options.value[nextIndex]
  if (!nextOption) return

  emit('update:modelValue', nextOption.value as ClinicalMode)
  nextTick(() => {
    tablist.value
      ?.querySelector<HTMLButtonElement>('[data-clinical-mode="' + nextOption.value + '"]')
      ?.focus()
  })
}
</script>

<template>
  <div
    ref="tablist"
    class="clinical-mode-nav grid grid-cols-2 gap-2 md:grid-cols-4"
    role="tablist"
    :aria-label="t('patientDetail.tabs.clinical')"
  >
    <button
      v-for="(option, index) in options"
      :id="'clinical-mode-' + option.value"
      :key="option.value"
      type="button"
      role="tab"
      :data-clinical-mode="option.value"
      :aria-selected="modelValue === option.value"
      aria-controls="clinical-mode-panel"
      :tabindex="modelValue === option.value ? 0 : -1"
      class="clinical-mode-button group flex min-w-0 items-center gap-2.5 rounded-token-lg border px-3 py-2.5 text-start"
      :class="{ 'is-active': modelValue === option.value }"
      @click="emit('update:modelValue', option.value as ClinicalMode)"
      @keydown="handleKeydown($event, index)"
    >
      <span
        class="clinical-mode-icon flex size-10 shrink-0 items-center justify-center rounded-token-md"
        :class="modelValue === option.value ? 'is-active' : ''"
      >
        <UIcon
          :name="option.icon"
          class="size-5"
        />
      </span>
      <span class="min-w-0 flex-1">
        <span class="clinical-mode-label block text-ui font-semibold leading-tight">
          {{ option.label }}
        </span>
      </span>
      <UBadge
        v-if="option.badge != null && option.badge !== ''"
        color="neutral"
        variant="subtle"
        size="xs"
        class="tnum shrink-0"
      >
        {{ option.badge }}
      </UBadge>
      <UIcon
        name="i-lucide-chevron-right"
        class="clinical-mode-chevron size-4 shrink-0 text-subtle"
        aria-hidden="true"
      />
    </button>
  </div>
</template>

<style scoped>
.clinical-mode-button {
  min-height: 3.75rem;
  border-color: var(--color-border);
  background-color: var(--color-surface);
  color: var(--color-text-muted);
  transition:
    border-color 160ms ease,
    background-color 160ms ease,
    box-shadow 160ms ease,
    color 160ms ease;
  touch-action: manipulation;
}

.clinical-mode-button:hover {
  border-color: var(--color-border-strong);
  background-color: var(--color-surface-muted);
  color: var(--color-text);
}

.clinical-mode-button:focus-visible {
  outline: 3px solid color-mix(in oklab, var(--color-primary-accent) 42%, transparent);
  outline-offset: 2px;
}

.clinical-mode-button.is-active {
  border-color: var(--color-primary-accent);
  background-color: var(--color-primary-soft);
  color: var(--color-primary-soft-text);
  box-shadow: var(--shadow-xs);
}

.clinical-mode-icon {
  background-color: var(--color-surface-muted);
  color: var(--color-text-muted);
}

.clinical-mode-icon.is-active {
  background-color: var(--color-surface);
  color: var(--color-primary-accent);
}

.clinical-mode-chevron {
  transition: transform 160ms ease;
}

.clinical-mode-button.is-active .clinical-mode-chevron {
  color: var(--color-primary-accent);
  transform: translateX(2px);
}

@media (prefers-reduced-motion: reduce) {
  .clinical-mode-button,
  .clinical-mode-chevron {
    transition: none;
  }
}
</style>
