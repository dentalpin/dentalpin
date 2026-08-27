<script setup lang="ts">
/**
 * "Getting started" card on the dashboard (admins only; registered as a
 * `dashboard.hero` slot entry by the host). Lists the required steps with
 * progress, an optional group, inline mini-modals for the steps that
 * provide one, and the entry point to guided mode.
 *
 * Auto-hides once dismissed or completed (server-side, per clinic).
 */
import type { Component } from 'vue'
import type { GettingStartedItem } from '~/composables/useSettingsRegistry'

const { t } = useI18n()
const toast = useToast()
const onboarding = useOnboarding()

const showOptional = ref(false)

const isVisible = computed(() =>
  onboarding.isAdmin.value
  && !onboarding.isDismissed.value
  && onboarding.required.value.length > 0
)

const percent = computed(() => {
  if (!onboarding.loaded.value) return 0
  const { done, total } = onboarding.progress.value
  return total ? Math.round((done / total) * 100) : 0
})

// ---- Mini-modals ------------------------------------------------------
const modalCache = new Map<string, Component>()
const activeStep = computed(() =>
  onboarding.activeModalId.value
    ? onboarding.steps.value.find(s => s.id === onboarding.activeModalId.value) ?? null
    : null
)
const activeModal = computed<Component | null>(() => {
  const step = activeStep.value
  if (!step?.modal) return null
  if (!modalCache.has(step.id)) {
    modalCache.set(step.id, defineAsyncComponent(step.modal))
  }
  return modalCache.get(step.id) ?? null
})
const modalOpen = computed({
  get: () => activeModal.value !== null,
  set: (v: boolean) => {
    if (!v) onboarding.closeModal()
  }
})

function act(step: GettingStartedItem) {
  if (step.modal) onboarding.openModal(step.id)
  else navigateTo(onboarding.stepRoute(step))
}

async function onSaved() {
  await onboarding.refresh(true)
}

// Completion: once every required step is resolved/skipped, persist and celebrate once.
watch(onboarding.isComplete, async (done) => {
  if (done && !onboarding.state.value.completed_at) {
    await onboarding.complete()
    toast.add({ title: t('onboarding.completedTitle'), description: t('onboarding.completedDescription'), color: 'success' })
  }
})

onMounted(() => {
  onboarding.refresh()
})
</script>

<template>
  <section
    v-if="isVisible"
    class="md:col-span-2 lg:col-span-3 rounded-[var(--radius-lg)] ring-1 ring-[var(--color-border)] bg-(--color-surface) p-4 sm:p-5"
    :aria-label="t('onboarding.title')"
  >
    <header class="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 mb-3">
      <div class="flex items-center gap-2 min-w-0 flex-1">
        <UIcon
          name="i-lucide-rocket"
          class="w-5 h-5 text-(--color-primary) shrink-0"
        />
        <div class="min-w-0">
          <h2 class="text-h3 text-default">
            {{ t('onboarding.title') }}
          </h2>
          <p class="text-caption text-muted">
            {{ onboarding.loaded.value ? t('onboarding.progress', onboarding.progress.value) : '…' }}
          </p>
        </div>
      </div>
      <div class="flex items-center gap-3 sm:w-64">
        <UProgress
          :model-value="percent"
          size="sm"
          class="flex-1"
          :aria-label="t('onboarding.progress', onboarding.progress.value)"
        />
        <span class="text-caption text-muted tabular-nums shrink-0">{{ percent }}%</span>
        <UButton
          icon="i-lucide-x"
          size="xs"
          variant="ghost"
          color="neutral"
          :aria-label="t('onboarding.dismiss')"
          @click="onboarding.dismiss()"
        />
      </div>
    </header>

    <div
      v-if="!onboarding.loaded.value"
      class="space-y-2 py-1"
      aria-busy="true"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-9 w-full"
      />
    </div>

    <!-- Compact done state: the six ticks collapse into one line so the
         card stops dominating the dashboard the moment the last required
         step resolves (it fully disappears once closed / on navigation). -->
    <div
      v-else-if="onboarding.isComplete.value"
      class="flex items-center gap-3 py-2.5"
    >
      <UIcon
        name="i-lucide-party-popper"
        class="w-5 h-5 text-(--color-success-accent) shrink-0"
      />
      <div class="min-w-0 flex-1">
        <p class="text-body text-default">
          {{ t('onboarding.completedTitle') }}
        </p>
        <p class="text-caption text-muted">
          {{ t('onboarding.completedDescription') }}
        </p>
      </div>
      <UButton
        size="sm"
        variant="soft"
        color="neutral"
        class="min-h-[36px]"
        @click="onboarding.dismiss()"
      >
        {{ t('common.close') }}
      </UButton>
    </div>

    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="step in onboarding.required.value"
        :key="step.id"
        class="flex items-center gap-3 py-2.5 min-h-[44px]"
      >
        <UIcon
          :name="step.resolved ? 'i-lucide-circle-check' : step.skipped ? 'i-lucide-circle-minus' : (step.icon ?? 'i-lucide-circle')"
          class="w-5 h-5 shrink-0"
          :class="step.resolved ? 'text-(--color-success-accent)' : step.skipped ? 'text-subtle' : 'text-(--color-primary)'"
        />
        <div class="min-w-0 flex-1">
          <p
            class="text-body"
            :class="step.resolved || step.skipped ? 'text-muted' : 'text-default'"
          >
            {{ t(step.labelKey) }}
          </p>
          <p
            v-if="step.descriptionKey && !step.resolved && !step.skipped"
            class="text-caption text-muted truncate"
          >
            {{ t(step.descriptionKey) }}
          </p>
        </div>
        <template v-if="!step.resolved && !step.skipped">
          <UButton
            size="sm"
            variant="soft"
            color="primary"
            class="min-h-[36px]"
            @click="act(step)"
          >
            {{ t('onboarding.configure') }}
          </UButton>
          <UButton
            icon="i-lucide-eye-off"
            size="sm"
            variant="ghost"
            color="neutral"
            :aria-label="t('onboarding.skip')"
            :title="t('onboarding.skip')"
            @click="onboarding.skip(step.id)"
          />
        </template>
        <UButton
          v-else-if="step.skipped"
          size="xs"
          variant="ghost"
          color="neutral"
          @click="onboarding.unskip(step.id)"
        >
          {{ t('onboarding.unskip') }}
        </UButton>
      </li>
    </ul>

    <!-- Optional group -->
    <div
      v-if="onboarding.pendingOptional.value.length > 0"
      class="mt-2 border-t border-[var(--color-border-subtle)] pt-2"
    >
      <button
        type="button"
        class="flex items-center gap-2 text-caption text-muted min-h-[36px] w-full text-left"
        :aria-expanded="showOptional"
        @click="showOptional = !showOptional"
      >
        <UIcon
          :name="showOptional ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="w-4 h-4"
        />
        {{ t('onboarding.optional', { count: onboarding.pendingOptional.value.length }) }}
        <span
          v-if="!showOptional"
          class="truncate text-subtle"
        >
          · {{ onboarding.pendingOptional.value.map(s => t(s.labelKey)).join(' · ') }}
        </span>
      </button>
      <ul
        v-if="showOptional"
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <li
          v-for="step in onboarding.pendingOptional.value"
          :key="step.id"
          class="flex items-center gap-3 py-2.5 min-h-[44px]"
        >
          <UIcon
            :name="step.icon ?? 'i-lucide-circle'"
            class="w-5 h-5 shrink-0 text-subtle"
          />
          <div class="min-w-0 flex-1">
            <p class="text-body text-default">
              {{ t(step.labelKey) }}
            </p>
            <p
              v-if="step.descriptionKey"
              class="text-caption text-muted truncate"
            >
              {{ t(step.descriptionKey) }}
            </p>
          </div>
          <UButton
            size="sm"
            variant="ghost"
            color="primary"
            @click="act(step)"
          >
            {{ t('onboarding.configure') }}
          </UButton>
          <UButton
            icon="i-lucide-eye-off"
            size="sm"
            variant="ghost"
            color="neutral"
            :aria-label="t('onboarding.skip')"
            :title="t('onboarding.skip')"
            @click="onboarding.skip(step.id)"
          />
        </li>
      </ul>
    </div>

    <footer
      v-if="onboarding.pendingRequired.value.length > 0"
      class="flex items-center justify-end gap-2 mt-3"
    >
      <UButton
        variant="ghost"
        color="neutral"
        size="sm"
        @click="onboarding.dismiss()"
      >
        {{ t('onboarding.dismiss') }}
      </UButton>
      <UButton
        icon="i-lucide-play"
        size="sm"
        color="primary"
        @click="onboarding.start()"
      >
        {{ t('onboarding.guidedMode') }}
      </UButton>
    </footer>

    <component
      :is="activeModal"
      v-if="activeModal"
      v-model:open="modalOpen"
      @saved="onSaved"
    />
  </section>
</template>
