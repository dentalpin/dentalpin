<script setup lang="ts">
import type { SemanticRole } from '~/config/severity'

export interface EntityChip {
  key: string
  role: SemanticRole
  label: string
  icon?: string
  dot?: boolean
  trailingIcon?: string
  ariaLabel?: string
  onClick?: () => void
}

interface Props {
  chips: EntityChip[]
  size?: 'xs' | 'sm' | 'md'
}

withDefaults(defineProps<Props>(), {
  size: 'sm'
})

function handleClick(chip: EntityChip) {
  chip.onClick?.()
}
</script>

<template>
  <div class="flex flex-wrap items-center gap-1.5">
    <span
      v-for="chip in chips"
      :key="chip.key"
      :role="chip.onClick ? 'button' : undefined"
      :tabindex="chip.onClick ? 0 : undefined"
      :aria-label="chip.onClick ? (chip.ariaLabel ?? chip.label) : undefined"
      :class="[
        'inline-flex items-center rounded-md',
        chip.onClick ? 'cursor-pointer focus:outline-none focus-visible:ring-2 focus-visible:ring-(--color-primary)' : ''
      ]"
      @click="handleClick(chip)"
      @keydown.enter.space.prevent="handleClick(chip)"
    >
      <StatusBadge
        :role="chip.role"
        :label="chip.label"
        :icon="chip.icon"
        :dot="chip.dot"
        :trailing-icon="chip.trailingIcon"
        :size="size"
      />
    </span>
  </div>
</template>
