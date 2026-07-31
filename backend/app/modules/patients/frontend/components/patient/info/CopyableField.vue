<script setup lang="ts">
interface Props {
  icon: string
  label: string
  value?: string | null
  copyAriaLabel: string
  href?: string
  placeholder?: string
}

const props = withDefaults(defineProps<Props>(), {
  value: null,
  href: undefined,
  placeholder: '—'
})

const { t } = useI18n()
const toast = useToast()

const hasValue = computed(() => props.value !== null && props.value !== undefined && props.value !== '')

async function copyValue() {
  if (!hasValue.value || !props.value) return
  try {
    await navigator.clipboard.writeText(props.value)
    toast.add({
      title: t('common.copied'),
      color: 'success',
      icon: 'i-lucide-check'
    })
  } catch {
    /* clipboard not available; silently ignore */
  }
}
</script>

<template>
  <div class="flex items-start gap-3 py-2">
    <UIcon
      :name="icon"
      class="w-4 h-4 text-subtle shrink-0 mt-1"
      aria-hidden="true"
    />
    <div class="flex-1 min-w-0 flex flex-col sm:flex-row sm:items-center sm:gap-3">
      <dt class="text-caption text-subtle sm:w-32 sm:shrink-0">
        {{ label }}
      </dt>
      <dd class="text-body text-default min-w-0 break-words">
        <a
          v-if="hasValue && href"
          :href="href"
          class="text-primary-accent hover:underline"
        >
          {{ value }}
        </a>
        <span v-else-if="hasValue">{{ value }}</span>
        <span
          v-else
          class="text-subtle"
        >{{ placeholder }}</span>
      </dd>
    </div>
    <UButton
      v-if="hasValue"
      variant="ghost"
      color="neutral"
      size="sm"
      icon="i-lucide-copy"
      :aria-label="copyAriaLabel"
      class="shrink-0"
      @click="copyValue"
    />
  </div>
</template>
