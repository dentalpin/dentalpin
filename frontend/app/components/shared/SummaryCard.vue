<script setup lang="ts">
/**
 * SummaryCard — consistent shell for patient-summary smart-cards.
 *
 * Each card renders an icon + title row, an optional severity stripe
 * on the left edge (danger/warning/success/info), a snapshot body and
 * an optional footer CTA that turns the whole card into a deep link.
 * Loading and empty states are first-class.
 *
 * Pattern: the cards live in their owning modules (PlanCard in
 * treatment_plan, BalanceCard in payments, etc.) and use this shell
 * for visual consistency. The shell is in the host app so any module
 * can use it without a cross-module import.
 */
type Severity = 'neutral' | 'info' | 'success' | 'warning' | 'danger'

interface Props {
  title: string
  icon?: string
  severity?: Severity
  /** Optional href — when set, the card is clickable and the whole body is the target. */
  to?: string
  /** Loading skeleton. Overrides empty/body. */
  loading?: boolean
  /** Show empty state slot instead of default body. */
  empty?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  severity: 'neutral',
  loading: false,
  empty: false
})

const severityStripe = computed(() => {
  switch (props.severity) {
    case 'danger':
      return 'before:bg-[var(--color-danger-accent)]'
    case 'warning':
      return 'before:bg-[var(--color-warning-accent)]'
    case 'success':
      return 'before:bg-[var(--color-success-accent)]'
    case 'info':
      return 'before:bg-[var(--color-primary-accent)]'
    default:
      return 'before:bg-transparent'
  }
})

const iconColor = computed(() => {
  switch (props.severity) {
    case 'danger':
      return 'text-[var(--color-danger-accent)]'
    case 'warning':
      return 'text-[var(--color-warning-accent)]'
    case 'success':
      return 'text-[var(--color-success-accent)]'
    case 'info':
      return 'text-primary-accent'
    default:
      return 'text-subtle'
  }
})

const interactive = computed(() => !!props.to)
</script>

<template>
  <NuxtLink
    v-if="interactive"
    :to="to"
    class="summary-card relative flex flex-col rounded-token-lg border border-default bg-surface overflow-hidden transition-colors hover:bg-surface-muted cursor-pointer before:absolute before:start-0 before:top-0 before:bottom-0 before:w-1"
    :class="severityStripe"
  >
    <header class="flex items-center gap-2 px-4 pt-3 pb-1">
      <UIcon
        v-if="icon"
        :name="icon"
        class="w-4 h-4 shrink-0"
        :class="iconColor"
      />
      <span class="text-caption uppercase tracking-wide text-muted">
        {{ title }}
      </span>
      <slot name="header-trailing" />
    </header>

    <div class="flex-1 px-4 pb-3 min-w-0">
      <div
        v-if="loading"
        class="space-y-2"
      >
        <USkeleton class="h-5 w-3/4" />
        <USkeleton class="h-3 w-full" />
        <USkeleton class="h-3 w-1/2" />
      </div>
      <div
        v-else-if="empty"
        class="text-body text-muted"
      >
        <slot name="empty" />
      </div>
      <slot v-else />
    </div>

    <footer
      v-if="$slots.footer && !loading"
      class="px-4 py-2 border-t border-default text-caption text-primary-accent flex items-center justify-between gap-2 bg-surface-muted/40"
    >
      <slot name="footer" />
      <UIcon
        name="i-lucide-arrow-right"
        class="w-4 h-4 shrink-0"
      />
    </footer>
  </NuxtLink>

  <div
    v-else
    class="summary-card relative flex flex-col rounded-token-lg border border-default bg-surface overflow-hidden before:absolute before:start-0 before:top-0 before:bottom-0 before:w-1"
    :class="severityStripe"
  >
    <header class="flex items-center gap-2 px-4 pt-3 pb-1">
      <UIcon
        v-if="icon"
        :name="icon"
        class="w-4 h-4 shrink-0"
        :class="iconColor"
      />
      <span class="text-caption uppercase tracking-wide text-muted">
        {{ title }}
      </span>
      <slot name="header-trailing" />
    </header>

    <div class="flex-1 px-4 pb-3 min-w-0">
      <div
        v-if="loading"
        class="space-y-2"
      >
        <USkeleton class="h-5 w-3/4" />
        <USkeleton class="h-3 w-full" />
        <USkeleton class="h-3 w-1/2" />
      </div>
      <div
        v-else-if="empty"
        class="text-body text-muted"
      >
        <slot name="empty" />
      </div>
      <slot v-else />
    </div>

    <footer
      v-if="$slots.footer && !loading"
      class="px-4 py-2 border-t border-default text-caption text-muted flex items-center gap-2 bg-surface-muted/40"
    >
      <slot name="footer" />
    </footer>
  </div>
</template>
