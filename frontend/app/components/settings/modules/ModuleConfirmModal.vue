<script setup lang="ts">
import type { UiColor } from '~/config/severity'

type Variant = 'install' | 'uninstall' | 'upgrade' | 'apply'

interface Props {
  open: boolean
  variant: Variant
  moduleName?: string
  scheduled?: string[]
  loading?: boolean
  error?: string | null
  forceAvailable?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [force: boolean]
}>()
const { t } = useI18n()

const force = ref(false)

watch(
  () => props.open,
  (open) => {
    if (!open) {
      force.value = false
    }
  }
)

const iconByVariant: Record<Variant, string> = {
  install: 'i-lucide-download',
  uninstall: 'i-lucide-alert-triangle',
  upgrade: 'i-lucide-arrow-up-circle',
  apply: 'i-lucide-play'
}

const iconColorClass: Record<Variant, string> = {
  install: 'text-primary-accent',
  uninstall: 'text-danger-accent',
  upgrade: 'text-info-accent',
  apply: 'text-primary-accent'
}

const confirmColor: Record<Variant, UiColor> = {
  install: 'primary',
  uninstall: 'error',
  upgrade: 'info',
  apply: 'primary'
}

const titleKey = computed(() => {
  switch (props.variant) {
    case 'install':
      return 'settings.modules.confirmInstall.title'
    case 'uninstall':
      return 'settings.modules.confirmUninstall.title'
    case 'upgrade':
      return 'settings.modules.confirmUpgrade.title'
    case 'apply':
      return 'settings.modules.confirmApply.title'
  }
  return 'common.confirm'
})

const confirmLabelKey = computed(() => {
  switch (props.variant) {
    case 'install':
      return 'settings.modules.actions.install'
    case 'uninstall':
      return 'settings.modules.actions.uninstall'
    case 'upgrade':
      return 'settings.modules.actions.upgrade'
    case 'apply':
      return 'settings.modules.actions.apply'
  }
  return 'common.confirm'
})

function closeModal() {
  if (!props.loading) {
    emit('update:open', false)
  }
}

function onConfirm() {
  emit('confirm', force.value)
}
</script>

<template>
  <UModal
    :open="open"
    :dismissible="!loading"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <UCard>
        <template #header>
          <div class="flex items-center gap-2">
            <UIcon
              :name="iconByVariant[variant]"
              class="w-5 h-5"
              :class="iconColorClass[variant]"
            />
            <h3 class="font-semibold text-default">
              {{ t(titleKey, { name: moduleName ?? '' }) }}
            </h3>
          </div>
        </template>

        <div class="space-y-3">
          <p
            v-if="variant === 'install'"
            class="text-muted"
          >
            {{ t('settings.modules.confirmInstall.message', { name: moduleName ?? '' }) }}
          </p>

          <div
            v-if="variant === 'install' && scheduled && scheduled.length > 1"
            class="text-sm text-subtle"
          >
            <p class="font-semibold">
              {{ t('settings.modules.confirmInstall.scheduled') }}
            </p>
            <ul class="list-disc ps-5">
              <li
                v-for="dep in scheduled"
                :key="dep"
              >
                {{ dep }}
              </li>
            </ul>
          </div>

          <p
            v-if="variant === 'uninstall'"
            class="text-muted"
          >
            {{ t('settings.modules.confirmUninstall.warning', { name: moduleName ?? '' }) }}
          </p>

          <p
            v-if="variant === 'upgrade'"
            class="text-muted"
          >
            {{ t('settings.modules.confirmUpgrade.message', { name: moduleName ?? '' }) }}
          </p>

          <p
            v-if="variant === 'apply'"
            class="text-muted"
          >
            {{ t('settings.modules.confirmApply.message') }}
          </p>

          <div
            v-if="error"
            class="rounded-md bg-[var(--color-danger-soft)] p-3 text-sm text-danger-accent"
          >
            {{ error }}
          </div>

          <div
            v-if="variant === 'uninstall' && forceAvailable"
            class="pt-2 border-t border-default"
          >
            <label class="flex items-start gap-2 cursor-pointer">
              <UCheckbox v-model="force" />
              <span class="text-sm">
                <span class="font-medium text-danger-accent">
                  {{ t('settings.modules.actions.force') }}
                </span>
                <span class="block text-caption text-subtle">
                  {{ t('settings.modules.confirmUninstall.forceHint') }}
                </span>
              </span>
            </label>
          </div>
        </div>

        <div class="flex justify-end gap-2 pt-6">
          <UButton
            variant="ghost"
            :disabled="loading"
            @click="closeModal"
          >
            {{ t('common.cancel') }}
          </UButton>
          <UButton
            :color="confirmColor[variant]"
            :loading="loading"
            @click="onConfirm"
          >
            {{ t(confirmLabelKey) }}
          </UButton>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
