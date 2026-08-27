<script setup lang="ts">
/**
 * Sticky "Step N of M" bar shown while guided mode is active
 * (`?onboarding=<ruleId>` on the current route). Mounted once in the
 * default layout above the module banners.
 */
const { t } = useI18n()
const toast = useToast()
const onboarding = useOnboarding()

const isLast = computed(() =>
  onboarding.pendingRequired.value.every(s => s.id === onboarding.currentStepId.value)
)

async function onNext() {
  const more = await onboarding.next()
  if (!more) {
    toast.add({ title: t('onboarding.guidedDoneTitle'), description: t('onboarding.guidedDoneDescription'), color: 'success' })
  }
}
</script>

<template>
  <div
    v-if="onboarding.isGuided.value && onboarding.currentStep.value"
    class="sticky top-0 z-30 -mx-3 sm:-mx-4 md:-mx-6 mb-3 px-3 sm:px-4 md:px-6 py-2 bg-(--color-surface) border-b border-[var(--color-border)] flex items-center gap-3"
    role="region"
    :aria-label="t('onboarding.guidedMode')"
  >
    <UIcon
      name="i-lucide-rocket"
      class="w-4 h-4 text-(--color-primary) shrink-0"
    />
    <p class="text-body text-default min-w-0 flex-1 truncate">
      <span class="text-muted">
        {{ t('onboarding.stepOf', onboarding.guidedProgress.value) }}
      </span>
      <span class="mx-1.5 text-subtle">·</span>
      <span class="font-medium">{{ t(onboarding.currentStep.value.labelKey) }}</span>
    </p>
    <UButton
      variant="ghost"
      color="neutral"
      size="sm"
      class="min-h-[40px]"
      @click="onboarding.exit()"
    >
      {{ t('onboarding.exit') }}
    </UButton>
    <UButton
      color="primary"
      size="sm"
      class="min-h-[40px]"
      :trailing-icon="isLast ? 'i-lucide-check' : 'i-lucide-arrow-right'"
      @click="onNext"
    >
      {{ isLast ? t('onboarding.finish') : t('onboarding.next') }}
    </UButton>
  </div>
</template>
