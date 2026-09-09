<script setup lang="ts">
// Global launcher: a floating button + the slide-over drawer, plus the
// Cmd/Ctrl+K shortcut. Teleports to <body> via UButton (fixed) and
// USlideover (portal), so it overlays every page.
const { t } = useI18n()
const { open, toggle, messages, busy, reset } = useCopilot()

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    toggle()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <ClientOnly>
    <UButton
      class="fixed bottom-4 end-4 z-40 rounded-full shadow-lg"
      icon="i-lucide-sparkles"
      size="lg"
      color="primary"
      :aria-label="t('copilot.open')"
      @click="toggle"
    />

    <USlideover
      :open="open"
      side="right"
      :ui="{ content: 'w-full sm:w-[480px] max-w-[95vw]' }"
      @update:open="(v: boolean) => (open = v)"
    >
      <template #content>
        <div class="flex h-full flex-col">
          <header class="flex h-14 items-center justify-between border-b border-default px-4">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-sparkles"
                class="text-primary"
              />
              <span class="font-semibold">{{ t('copilot.title') }}</span>
            </div>
            <div class="flex items-center gap-1">
              <UButton
                v-if="messages.length"
                icon="i-lucide-plus"
                color="neutral"
                variant="ghost"
                size="sm"
                :disabled="busy"
                :aria-label="t('copilot.new')"
                @click="reset"
              />
              <UButton
                icon="i-lucide-x"
                color="neutral"
                variant="ghost"
                size="sm"
                :aria-label="t('copilot.confirm.reject')"
                @click="open = false"
              />
            </div>
          </header>
          <div class="flex-1 overflow-hidden p-3">
            <CopilotDrawer />
          </div>
        </div>
      </template>
    </USlideover>
  </ClientOnly>
</template>
