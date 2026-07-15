<script setup lang="ts">
import type { ModuleInfo, ModuleOperationLogEntry } from '~/types'
import type { UiColor } from '~/config/severity'

interface Props {
  open: boolean
  module: ModuleInfo | null
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
}>()
const { t, d } = useI18n()
const { operations } = useModuleAdmin()

const logEntries = ref<ModuleOperationLogEntry[]>([])
const loadingLog = ref(false)
const logError = ref<string | null>(null)

const manifestJson = computed(() => JSON.stringify(props.module, null, 2))

async function fetchLog() {
  if (!props.module) {
    return
  }
  loadingLog.value = true
  logError.value = null
  try {
    logEntries.value = await operations(props.module.name, 20)
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }, message?: string }
    logError.value = e?.data?.detail ?? e?.message ?? t('common.error')
    logEntries.value = []
  } finally {
    loadingLog.value = false
  }
}

watch(
  () => [props.open, props.module?.name],
  ([open]) => {
    if (open && props.module) {
      fetchLog()
    }
  }
)

function closeModal() {
  emit('update:open', false)
}

function formatDate(value: string | null): string {
  if (!value) {
    return '—'
  }
  try {
    return d(new Date(value), 'short')
  } catch {
    return value
  }
}

function statusColor(status: string): UiColor {
  if (status === 'completed') {
    return 'success'
  }
  if (status === 'failed') {
    return 'error'
  }
  return 'neutral'
}
</script>

<template>
  <UModal
    :open="open"
    :ui="{ content: 'sm:max-w-3xl' }"
    @update:open="emit('update:open', $event)"
  >
    <template #content>
      <UCard v-if="module">
        <template #header>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-puzzle"
                class="w-5 h-5 text-primary-accent"
              />
              <h3 class="font-semibold text-default">
                {{ module.name }}
                <span class="text-caption text-subtle">v{{ module.version }}</span>
              </h3>
            </div>
            <UButton
              icon="i-lucide-x"
              variant="ghost"
              size="xs"
              @click="closeModal"
            />
          </div>
        </template>

        <div class="space-y-5">
          <!-- Key facts grid -->
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.state') }}
              </p>
              <p class="text-default">
                {{ module.state }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.category') }}
              </p>
              <p class="text-default">
                {{ t(`settings.modules.category.${module.category}`) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.installedAt') }}
              </p>
              <p class="text-default">
                {{ formatDate(module.installed_at) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.lastChange') }}
              </p>
              <p class="text-default">
                {{ formatDate(module.last_state_change) }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.baseRevision') }}
              </p>
              <p class="text-default font-mono text-xs">
                {{ module.base_revision ?? '—' }}
              </p>
            </div>
            <div>
              <p class="text-caption text-subtle">
                {{ t('settings.modules.detail.appliedRevision') }}
              </p>
              <p class="text-default font-mono text-xs">
                {{ module.applied_revision ?? '—' }}
              </p>
            </div>
          </div>

          <div
            v-if="module.error_message"
            class="rounded-md bg-[var(--color-danger-soft)] p-3 text-sm"
          >
            <p class="font-semibold text-danger-accent">
              {{ t('settings.modules.detail.errorMessage') }}
            </p>
            <p class="mt-1 text-danger-accent">
              {{ module.error_message }}
            </p>
          </div>

          <!-- Operation log -->
          <div>
            <div class="flex items-center justify-between mb-2">
              <h4 class="font-semibold text-default">
                {{ t('settings.modules.detail.operationLog') }}
              </h4>
              <UButton
                size="xs"
                variant="ghost"
                icon="i-lucide-refresh-cw"
                :loading="loadingLog"
                @click="fetchLog"
              >
                {{ t('common.refresh') }}
              </UButton>
            </div>

            <div
              v-if="logError"
              class="text-sm text-danger-accent"
            >
              {{ logError }}
            </div>

            <div
              v-else-if="loadingLog && logEntries.length === 0"
              class="space-y-2"
            >
              <USkeleton class="h-6 w-full" />
              <USkeleton class="h-6 w-full" />
            </div>

            <p
              v-else-if="logEntries.length === 0"
              class="text-caption text-subtle"
            >
              {{ t('settings.modules.detail.noOperations') }}
            </p>

            <div
              v-else
              class="space-y-1 max-h-64 overflow-y-auto"
            >
              <div
                v-for="entry in logEntries"
                :key="entry.id"
                class="grid grid-cols-12 gap-2 text-xs py-1 border-b border-default last:border-0"
              >
                <span class="col-span-3 text-subtle">{{ formatDate(entry.created_at) }}</span>
                <span class="col-span-2 font-mono">{{ entry.operation }}</span>
                <span class="col-span-3 font-mono">{{ entry.step }}</span>
                <span class="col-span-2">
                  <UBadge
                    :color="statusColor(entry.status)"
                    size="xs"
                    variant="subtle"
                  >
                    {{ entry.status }}
                  </UBadge>
                </span>
                <span
                  v-if="entry.details"
                  class="col-span-2 truncate text-subtle"
                  :title="JSON.stringify(entry.details)"
                >
                  {{ JSON.stringify(entry.details) }}
                </span>
              </div>
            </div>
          </div>

          <!-- Raw manifest snapshot -->
          <details>
            <summary class="cursor-pointer font-semibold text-default">
              {{ t('settings.modules.detail.manifest') }}
            </summary>
            <pre class="mt-2 text-xs bg-[var(--color-bg-muted)] rounded p-3 overflow-auto max-h-64">{{ manifestJson }}</pre>
          </details>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
