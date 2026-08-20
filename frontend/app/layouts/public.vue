<script setup lang="ts">
/**
 * Patient-facing layout — no app sidebar, no sticky chrome.
 * Used by ``/p/budget/<token>`` (ADR 0006). Mobile-first.
 */
import { APP_NAME } from '~/constants/branding'
</script>

<template>
  <div class="min-h-screen bg-[var(--ui-bg)] flex flex-col">
    <header class="border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]">
      <div class="max-w-3xl mx-auto px-4 py-3 flex items-center gap-2">
        <UIcon
          name="i-lucide-tooth"
          class="w-6 h-6 text-[var(--ui-primary)]"
        />
        <span class="font-semibold tracking-tight">{{ APP_NAME }}</span>
      </div>
    </header>
    <main class="flex-1">
      <slot />
    </main>
    <footer class="border-t border-[var(--ui-border)] py-4 text-center text-xs text-[var(--ui-text-muted)]">
      <span>{{ APP_NAME }} · {{ new Date().getFullYear() }}</span>
    </footer>
  </div>
</template>
