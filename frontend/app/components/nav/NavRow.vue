<script setup lang="ts">
/**
 * Single navigation row (issue #232): shared by the sidebar and the
 * mobile drawer, flat and grouped alike. `padded` selects the
 * density — compact rows in the sidebar, 44 px rows in the drawer.
 */
defineProps<{
  to: string
  label: string
  icon: string
  active: boolean
  padded?: 'compact' | 'roomy'
  hideLabel?: boolean
  badge?: number
}>()
</script>

<template>
  <NuxtLink
    :to="to"
    :aria-label="badge ? `${label} (${badge})` : label"
    :title="hideLabel ? label : undefined"
    class="group relative flex items-center gap-3 px-3 rounded-token-md text-ui transition-colors"
    :class="[
      padded === 'roomy' ? 'py-3' : 'py-2',
      active
        ? 'bg-[var(--color-primary-soft)] text-[var(--color-primary-soft-text)]'
        : 'text-muted hover:bg-surface hover:text-default'
    ]"
  >
    <UIcon
      :name="icon"
      class="shrink-0"
      :class="padded === 'roomy' ? 'w-5 h-5' : 'w-[18px] h-[18px]'"
    />
    <span
      v-if="!hideLabel"
      class="truncate"
    >{{ label }}</span>
    <UBadge
      v-if="badge"
      :class="hideLabel ? 'absolute -right-1 -top-1' : 'ms-auto'"
      size="sm"
      color="primary"
      variant="soft"
    >
      {{ badge > 99 ? '99+' : badge }}
    </UBadge>
  </NuxtLink>
</template>
