<script setup lang="ts">
interface Props {
  title: string
  subtitle?: string
}

defineProps<Props>()
</script>

<template>
  <header class="mb-6">
    <!--
      <sm the actions stack under the title: sharing the row squeezed
      long titles ("Buenas tardes, Marcos" + date) into a 6-line wrap
      next to two buttons at 375px (#203).
    -->
    <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
      <div class="min-w-0">
        <h1 class="text-display text-default text-pretty">
          {{ title }}
        </h1>
        <p
          v-if="subtitle"
          class="mt-1 text-body text-muted text-pretty"
        >
          {{ subtitle }}
        </p>
      </div>
      <div
        v-if="$slots.actions"
        class="flex flex-wrap items-center gap-2 sm:shrink-0"
      >
        <slot name="actions" />
      </div>
    </div>
    <div
      v-if="$slots.tabs"
      class="mt-4"
    >
      <slot name="tabs" />
    </div>
  </header>
</template>
