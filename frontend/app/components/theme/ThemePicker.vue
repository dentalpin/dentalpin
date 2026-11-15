<script setup lang="ts">
import { DENTUM_THEME_OPTIONS, type DentumTheme } from '~/composables/useDentumTheme'

const { t } = useI18n()
const { theme, setTheme } = useDentumTheme()
const open = ref(false)

function chooseTheme(value: DentumTheme) {
  setTheme(value)
  open.value = false
}
</script>

<template>
  <UPopover
    v-model:open="open"
    :ui="{ content: 'max-w-[90vw] bg-surface ring-1 ring-[var(--color-border)] shadow-lg' }"
  >
    <UButton
      variant="ghost"
      color="neutral"
      size="sm"
      icon="i-lucide-palette"
      :aria-label="t('appearance.pickerLabel')"
      :title="t('appearance.pickerLabel')"
      aria-haspopup="dialog"
    />

    <template #content>
      <div class="w-72 max-w-[90vw] p-2">
        <p class="px-2 py-2 text-sm font-semibold text-default">
          {{ t('appearance.pickerTitle') }}
        </p>

        <div
          class="flex flex-col gap-1"
          role="group"
          :aria-label="t('appearance.pickerTitle')"
        >
          <button
            v-for="option in DENTUM_THEME_OPTIONS"
            :key="option.id"
            type="button"
            class="flex min-h-11 items-center gap-3 rounded-md px-3 text-start text-sm transition-colors hover:bg-surface-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-primary)"
            :class="theme === option.id ? 'bg-(--color-primary-soft) text-(--color-primary-soft-text)' : 'text-default'"
            :aria-pressed="theme === option.id"
            @click="chooseTheme(option.id)"
          >
            <span
              class="size-5 shrink-0 rounded-full ring-1 ring-black/10 dark:ring-white/20"
              :style="{ backgroundColor: option.swatch }"
              aria-hidden="true"
            />
            <span class="min-w-0 flex-1 truncate">
              {{ t(option.labelKey) }}
            </span>
            <UIcon
              v-if="theme === option.id"
              name="i-lucide-check"
              class="size-4 shrink-0"
              aria-hidden="true"
            />
          </button>
        </div>
      </div>
    </template>
  </UPopover>
</template>
