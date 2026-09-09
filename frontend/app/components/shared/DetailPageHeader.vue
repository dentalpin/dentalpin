<script setup lang="ts">
interface BackTo {
  to: string
  label: string
}

interface Props {
  title: string
  version?: string | number
  subtitle?: string
  backTo?: BackTo
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  loading: false
})
</script>

<template>
  <header>
    <UButton
      v-if="backTo"
      variant="ghost"
      color="neutral"
      icon="i-lucide-arrow-left"
      size="sm"
      :to="backTo.to"
      class="-ms-2 mb-3"
    >
      {{ backTo.label }}
    </UButton>

    <div
      v-if="loading"
      class="space-y-3"
      aria-busy="true"
    >
      <USkeleton class="h-9 w-64" />
      <USkeleton class="h-5 w-40" />
    </div>

    <div
      v-else
      class="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4"
    >
      <div class="min-w-0 flex-1">
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <h1 class="text-display text-default text-pretty">
            {{ title }}
          </h1>
          <span
            v-if="version != null && version !== ''"
            class="text-subtle"
          >v{{ version }}</span>
          <slot name="status" />
        </div>

        <div
          v-if="$slots.subtitle || subtitle"
          class="mt-1"
        >
          <slot name="subtitle">
            <p class="text-body text-muted text-pretty">
              {{ subtitle }}
            </p>
          </slot>
        </div>
      </div>

      <div
        v-if="$slots.actions"
        class="shrink-0"
      >
        <slot name="actions" />
      </div>
    </div>
  </header>
</template>
