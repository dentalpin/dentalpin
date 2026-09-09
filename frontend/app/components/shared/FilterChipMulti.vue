<script setup lang="ts">
/**
 * FilterChipMulti — single-button multi-select chip.
 *
 * Rewritten on UPopover + a custom checkable list so the chip renders
 * as ONE control. Previous USelectMenu approach exposed the library's
 * own trigger alongside the custom UButton, producing a duplicate
 * widget per chip (Estado + extra chevron, Cobro + extra chevron…).
 *
 * Contract is unchanged: ``v-model:value=string[]``. ``multiple=false``
 * makes it behave as a single-select (one click sets, click on selected
 * clears).
 */
interface Option {
  label: string
  value: string
}

interface Props {
  label: string
  modelValue: string[]
  items: Option[]
  /** Optional icon left of the label. */
  icon?: string
  /** When false the chip behaves as a single-select. */
  multiple?: boolean
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  icon: undefined,
  multiple: true,
  disabled: false
})

const emit = defineEmits<{
  'update:modelValue': [value: string[]]
}>()

const isOpen = ref(false)

const isActive = computed(() => props.modelValue.length > 0)

const displayLabel = computed(() => {
  if (!props.modelValue.length) return props.label
  if (!props.multiple && props.modelValue.length === 1) {
    const sel = props.items.find(i => i.value === props.modelValue[0])
    return sel ? `${props.label}: ${sel.label}` : props.label
  }
  return `${props.label} · ${props.modelValue.length}`
})

function isSelected(value: string): boolean {
  return props.modelValue.includes(value)
}

function toggle(value: string) {
  if (props.multiple) {
    const next = isSelected(value)
      ? props.modelValue.filter(v => v !== value)
      : [...props.modelValue, value]
    emit('update:modelValue', next)
    return
  }
  // single-select: clicking selected clears; otherwise replace.
  const next = isSelected(value) ? [] : [value]
  emit('update:modelValue', next)
  isOpen.value = false
}

function clear() {
  emit('update:modelValue', [])
  isOpen.value = false
}
</script>

<template>
  <UPopover v-model:open="isOpen">
    <UButton
      :color="isActive ? 'primary' : 'neutral'"
      :variant="isActive ? 'soft' : 'outline'"
      size="sm"
      :icon="icon"
      :disabled="disabled"
      trailing-icon="i-lucide-chevron-down"
    >
      {{ displayLabel }}
    </UButton>

    <template #content>
      <div class="p-1 w-[220px] max-h-72 overflow-y-auto">
        <button
          v-for="opt in items"
          :key="opt.value"
          type="button"
          class="w-full text-start px-2 py-1.5 rounded-token-sm hover:bg-surface-muted focus-visible:bg-surface-muted focus-visible:outline-none flex items-center gap-2 text-ui"
          :class="isSelected(opt.value) ? 'text-default' : 'text-muted'"
          @click="toggle(opt.value)"
        >
          <UIcon
            :name="isSelected(opt.value) ? 'i-lucide-check' : 'i-lucide-circle'"
            class="w-4 h-4 shrink-0"
            :class="isSelected(opt.value) ? 'text-[var(--color-primary)]' : 'text-subtle'"
          />
          <span class="flex-1 truncate">{{ opt.label }}</span>
        </button>
        <div
          v-if="isActive"
          class="border-t border-subtle mt-1 pt-1"
        >
          <button
            type="button"
            class="w-full text-start px-2 py-1.5 rounded-token-sm hover:bg-surface-muted text-caption text-subtle"
            @click="clear"
          >
            {{ $t('lists.filter.clear') }}
          </button>
        </div>
      </div>
    </template>
  </UPopover>
</template>
