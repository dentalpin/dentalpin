<script setup lang="ts">
/**
 * Patient-facing layout — no app sidebar, no sticky chrome.
 * Used by ``/p/budget/<token>`` (ADR 0006). Mobile-first.
 *
 * A page may set ``definePageMeta({ publicChrome: false })`` to drop the
 * DentalPin header and footer: the online booking page shows the clinic's own
 * branding and is embedded in the clinic website.
 */
const showChrome = computed(() => useRoute().meta.publicChrome !== false)
</script>

<template>
  <div class="min-h-screen bg-[var(--ui-bg)] flex flex-col">
    <header
      v-if="showChrome"
      class="border-b border-[var(--ui-border)] bg-[var(--ui-bg-elevated)]"
    >
      <div class="max-w-3xl mx-auto px-4 py-3 flex items-center gap-2">
        <UIcon
          name="i-lucide-tooth"
          class="w-6 h-6 text-[var(--ui-primary)]"
        />
        <span class="font-semibold tracking-tight">DentalPin</span>
      </div>
    </header>
    <main class="flex-1">
      <slot />
    </main>
    <footer
      v-if="showChrome"
      class="border-t border-[var(--ui-border)] py-4 text-center text-xs text-[var(--ui-text-muted)]"
    >
      <span>DentalPin · {{ new Date().getFullYear() }}</span>
    </footer>
  </div>
</template>
