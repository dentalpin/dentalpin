<script setup lang="ts">
const { t } = useI18n()
const { public: { demoMode } } = useRuntimeConfig()
const toast = useToast()

const DEMO_EMAIL = 'admin@demo.clinic'
const DEMO_PASSWORD = 'demo1234'

async function copy(value: string) {
  if (!import.meta.client) return
  try {
    await navigator.clipboard.writeText(value)
    toast.add({
      title: t('common.success'),
      description: t('demo.copied'),
      color: 'success'
    })
  } catch {
    // Clipboard may be unavailable (insecure context). Silent.
  }
}
</script>

<template>
  <div
    v-if="demoMode"
    class="alert-surface-info rounded-token-md px-4 py-3 mt-4 space-y-2"
  >
    <div class="flex items-center gap-2">
      <UIcon
        name="i-lucide-info"
        class="w-4 h-4 shrink-0"
        :style="{ color: 'var(--color-info-accent)' }"
      />
      <span class="text-ui font-medium">
        {{ t('demo.credentialsTitle') }}
      </span>
    </div>
    <div class="space-y-1 text-body">
      <button
        type="button"
        class="flex items-center gap-2 w-full text-start hover:bg-surface rounded-token-sm px-2 py-1 transition-colors"
        :aria-label="t('demo.copyEmail')"
        @click="copy(DEMO_EMAIL)"
      >
        <span class="text-subtle w-20 shrink-0">{{ t('auth.email') }}:</span>
        <code class="font-mono text-default flex-1">{{ DEMO_EMAIL }}</code>
        <UIcon
          name="i-lucide-copy"
          class="w-3.5 h-3.5 text-subtle shrink-0"
        />
      </button>
      <button
        type="button"
        class="flex items-center gap-2 w-full text-start hover:bg-surface rounded-token-sm px-2 py-1 transition-colors"
        :aria-label="t('demo.copyPassword')"
        @click="copy(DEMO_PASSWORD)"
      >
        <span class="text-subtle w-20 shrink-0">{{ t('auth.password') }}:</span>
        <code class="font-mono text-default flex-1">{{ DEMO_PASSWORD }}</code>
        <UIcon
          name="i-lucide-copy"
          class="w-3.5 h-3.5 text-subtle shrink-0"
        />
      </button>
    </div>
    <p class="text-caption text-subtle">
      {{ t('demo.credentialsNote') }}
    </p>
  </div>
</template>
