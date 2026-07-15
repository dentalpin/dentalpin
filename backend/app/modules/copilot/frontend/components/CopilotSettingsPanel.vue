<script setup lang="ts">
// Copilot settings: morning digest opt-in (+ redaction visibility).
// Mounted at /settings/integrations/copilot via the settings registry.
import type { ApiResponse } from '~~/app/types'

interface CopilotSettings {
  provider: string
  model: string
  redaction_enabled: boolean
  digest_enabled: boolean
  digest_hour: number
  digest_recipient_user_ids: string[]
}

interface ToolStat { tool_name: string, calls: number, errors: number }
interface CopilotMetrics {
  window_days: number
  total_tool_calls: number
  failed_tool_calls: number
  error_rate: number
  avg_execution_ms: number
  conversations: number
  top_tools: ToolStat[]
  period_input_tokens: number
  period_output_tokens: number
  monthly_token_limit: number | null
  token_usage_pct: number | null
}

const { t } = useI18n()

function toolDisplayName(name: string): string {
  const i18nKey = name.replace(/\./g, '_')
  const key = `copilot.settings.metrics.toolNames.${i18nKey}`
  const translated = t(key)
  return translated !== key ? translated : name
}
const toast = useToast()
const api = useApi()
const { users, fetchUsers } = useUsers()

const settings = ref<CopilotSettings | null>(null)
const metrics = ref<CopilotMetrics | null>(null)
const isLoading = ref(false)
const isSaving = ref(false)

const hourOptions = Array.from({ length: 24 }, (_, h) => ({
  label: `${String(h).padStart(2, '0')}:00`,
  value: h
}))

// Clinic members eligible as digest recipients. Each gets their own
// email scoped to their role permissions (RBAC parity).
const recipientOptions = computed(() =>
  users.value.map(u => ({
    label: `${u.first_name} ${u.last_name}`.trim() || u.email,
    value: u.id
  }))
)

const tokensUsedPct = computed(() =>
  metrics.value?.token_usage_pct != null ? Math.round(metrics.value.token_usage_pct * 100) : null
)
const errorRatePct = computed(() =>
  metrics.value ? Math.round(metrics.value.error_rate * 100) : 0
)

async function load() {
  isLoading.value = true
  try {
    const [res] = await Promise.all([
      api.get<ApiResponse<CopilotSettings>>('/api/v1/copilot/settings'),
      fetchUsers()
    ])
    settings.value = res.data
    // Observability is admin-only; ignore if forbidden.
    try {
      const m = await api.get<ApiResponse<CopilotMetrics>>('/api/v1/copilot/metrics?days=30')
      metrics.value = m.data
    } catch {
      metrics.value = null
    }
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

async function save() {
  if (!settings.value || isSaving.value) return
  isSaving.value = true
  try {
    const res = await api.patch<ApiResponse<CopilotSettings>>('/api/v1/copilot/settings', {
      digest_enabled: settings.value.digest_enabled,
      digest_hour: settings.value.digest_hour,
      digest_recipient_user_ids: settings.value.digest_recipient_user_ids
    })
    settings.value = res.data
    toast.add({ title: t('copilot.settings.saved'), color: 'success' })
  } catch {
    toast.add({ title: t('common.error'), color: 'error' })
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <div class="flex flex-col gap-6">
    <USkeleton
      v-if="isLoading && !settings"
      class="h-40 w-full"
    />

    <template v-if="settings">
      <UCard>
        <template #header>
          <div>
            <p class="font-medium">
              {{ t('copilot.settings.digest.title') }}
            </p>
            <p class="text-sm text-muted">
              {{ t('copilot.settings.digest.description') }}
            </p>
          </div>
        </template>

        <div class="flex flex-col gap-4">
          <UFormField :label="t('copilot.settings.digest.enabled')">
            <USwitch v-model="settings.digest_enabled" />
          </UFormField>

          <UFormField
            v-if="settings.digest_enabled"
            :label="t('copilot.settings.digest.hour')"
            :help="t('copilot.settings.digest.hourHelp')"
          >
            <USelect
              v-model="settings.digest_hour"
              :items="hourOptions"
              class="w-full sm:w-40"
            />
          </UFormField>

          <UFormField
            v-if="settings.digest_enabled"
            :label="t('copilot.settings.digest.recipients')"
            :help="t('copilot.settings.digest.recipientsHelp')"
          >
            <USelectMenu
              v-model="settings.digest_recipient_user_ids"
              :items="recipientOptions"
              value-key="value"
              multiple
              :placeholder="t('copilot.settings.digest.recipientsPlaceholder')"
              class="w-full sm:w-80"
            />
          </UFormField>

          <div>
            <UButton
              :loading="isSaving"
              @click="save"
            >
              {{ t('common.save') }}
            </UButton>
          </div>
        </div>
      </UCard>

      <UCard v-if="metrics">
        <template #header>
          <div>
            <p class="font-medium">
              {{ t('copilot.settings.metrics.title') }}
            </p>
            <p class="text-sm text-muted">
              {{ t('copilot.settings.metrics.description', { days: metrics.window_days }) }}
            </p>
          </div>
        </template>

        <div class="flex flex-col gap-4">
          <div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div>
              <p class="text-2xl font-semibold">
                {{ metrics.total_tool_calls }}
              </p>
              <p class="text-xs text-muted">
                {{ t('copilot.settings.metrics.toolCalls') }}
              </p>
            </div>
            <div>
              <p
                class="text-2xl font-semibold"
                :class="errorRatePct > 10 ? 'text-error' : ''"
              >
                {{ errorRatePct }}%
              </p>
              <p class="text-xs text-muted">
                {{ t('copilot.settings.metrics.errorRate') }}
              </p>
            </div>
            <div>
              <p class="text-2xl font-semibold">
                {{ metrics.avg_execution_ms }} ms
              </p>
              <p class="text-xs text-muted">
                {{ t('copilot.settings.metrics.avgLatency') }}
              </p>
            </div>
            <div>
              <p class="text-2xl font-semibold">
                {{ metrics.conversations }}
              </p>
              <p class="text-xs text-muted">
                {{ t('copilot.settings.metrics.conversations') }}
              </p>
            </div>
          </div>

          <div v-if="tokensUsedPct !== null">
            <div class="mb-1 flex justify-between text-sm">
              <span class="text-muted">{{ t('copilot.settings.metrics.tokenBudget') }}</span>
              <span>{{ tokensUsedPct }}%</span>
            </div>
            <UProgress
              :model-value="tokensUsedPct"
              :color="tokensUsedPct >= 80 ? 'warning' : 'primary'"
            />
          </div>

          <div v-if="metrics.top_tools.length">
            <p class="mb-2 text-sm font-medium">
              {{ t('copilot.settings.metrics.topTools') }}
            </p>
            <div class="flex flex-col gap-1 text-sm">
              <div
                v-for="tool in metrics.top_tools"
                :key="tool.tool_name"
                class="flex justify-between"
              >
                <span class="font-mono text-xs">{{ toolDisplayName(tool.tool_name) }}</span>
                <span class="text-muted">
                  {{ tool.calls }}
                  <template v-if="tool.errors">
                    · <span class="text-error">{{ tool.errors }} err</span>
                  </template>
                </span>
              </div>
            </div>
          </div>
        </div>
      </UCard>

      <UCard>
        <template #header>
          <p class="font-medium">
            {{ t('copilot.settings.engine.title') }}
          </p>
        </template>
        <div class="flex flex-col gap-2 text-sm">
          <div class="flex justify-between">
            <span class="text-muted">{{ t('copilot.settings.engine.provider') }}</span>
            <span>{{ settings.provider }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted">{{ t('copilot.settings.engine.model') }}</span>
            <span>{{ settings.model }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-muted">{{ t('copilot.settings.engine.redaction') }}</span>
            <UBadge
              :color="settings.redaction_enabled ? 'success' : 'warning'"
              variant="soft"
            >
              {{ settings.redaction_enabled ? t('copilot.settings.engine.redactionOn') : t('copilot.settings.engine.redactionOff') }}
            </UBadge>
          </div>
        </div>
      </UCard>
    </template>
  </div>
</template>
