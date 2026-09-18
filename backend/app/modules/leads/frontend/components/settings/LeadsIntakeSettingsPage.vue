<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import { useLeadsSettings, type LeadSettings } from '../../composables/useLeadsSettings'

/**
 * Settings -> Integrations -> "Formulario web".
 *
 * This page is where the daily cap lives (clinic data, not an env var):
 * a clinic must be able to raise its own ceiling during a campaign
 * without an admin editing .env and restarting containers. It also owns
 * the intake key — the same page, because the key is what the cap
 * protects and two places to rotate it is how two UIs drift.
 *
 * Mounted by the host's dynamic route /settings/[category]/[page].vue,
 * so no definePageMeta here.
 */
const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const config = useRuntimeConfig()
const { getSettings, updateSettings, rotateIntakeKey, setIntakeKeyActive } = useLeadsSettings()

/**
 * The clinic's website posts to the **API**, which is a different origin
 * from the app whenever they are not served together (dev, split hosts).
 * The backend deliberately returns the path only — it does not guess
 * hostnames — so the base comes from the app's own API base URL, never
 * from `window.location.origin` (that would hand the clinic's developer
 * a URL pointing at the SPA, which answers with a login redirect).
 * Empty base = same-origin deployment (Caddy in front of both).
 */
const apiBaseUrl = computed(() => String(config.public.apiBaseUrl || '').replace(/\/+$/, ''))

const canRead = computed(() => can(PERMISSIONS.leads.settingsRead))
const canWrite = computed(() => can(PERMISSIONS.leads.settingsWrite))

const loading = ref(true)
const savingCap = ref(false)
const rotating = ref(false)
const togglingKey = ref(false)
const settings = ref<LeadSettings | null>(null)
const capInput = ref<number>(200)
// Plaintext of a freshly rotated key: local state only, never re-fetched.
const freshKey = ref<string | null>(null)

const CAP_MAX = 5000

onMounted(async () => {
  if (!canRead.value) {
    loading.value = false
    return
  }
  await load()
})

async function load() {
  loading.value = true
  try {
    const response = await getSettings()
    settings.value = response.data
    capInput.value = response.data.daily_cap
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.settingsLoad')),
      color: 'error'
    })
  } finally {
    loading.value = false
  }
}

// The counter is a fact about *today*: a stale date means zero so far.
const countToday = computed(() => {
  const current = settings.value
  if (!current) return 0
  const today = new Date().toISOString().slice(0, 10)
  return current.day_count_date === today ? current.day_count : 0
})

const atLimit = computed(() => {
  const cap = settings.value?.daily_cap ?? 0
  return cap > 0 && countToday.value >= cap
})

const gaugeLabel = computed(() => {
  const cap = settings.value?.daily_cap ?? 0
  if (cap === 0) return t('leads.settings.unlimited', { count: countToday.value })
  return t('leads.settings.volume', { count: countToday.value, cap })
})

const intakeUrl = computed(() => {
  const path = settings.value?.intake_url
  if (!path) return ''
  if (apiBaseUrl.value) return `${apiBaseUrl.value}${path}`
  return import.meta.client ? `${window.location.origin}${path}` : path
})

const curlExample = computed(() => {
  const key = freshKey.value ?? `${settings.value?.key.key_prefix ?? 'lk_'}…`
  return [
    `curl -X POST ${intakeUrl.value} \\`,
    '  -H "Content-Type: application/json" \\',
    `  -H "X-Lead-Key: ${key}" \\`,
    `  -d '{"full_name":"Marta Ruiz","phone":"+34 600 111 222","email":"marta@example.com","motive":"Ortodoncia","description":"Instagram","availability_days":["tue","thu"],"availability_slot":"afternoon"}'`
  ].join('\n')
})

// An empty field must not silently mean "unlimited": the button is
// disabled and save() refuses, rather than turning "" into 0.
const capValid = computed(() => {
  const raw = capInput.value
  if (raw === null || raw === undefined || String(raw).trim() === '') return false
  return Number.isFinite(Number(raw))
})

async function saveCap() {
  if (!capValid.value) return
  const cap = Math.min(CAP_MAX, Math.max(0, Math.round(Number(capInput.value))))
  capInput.value = cap
  savingCap.value = true
  try {
    const response = await updateSettings(cap)
    settings.value = response.data
    toast.add({ title: t('leads.settings.capSaved'), color: 'success' })
  } catch (e: unknown) {
    // Let the server stay the authority (it validates 0..5000).
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.settingsSave')),
      color: 'error'
    })
  } finally {
    savingCap.value = false
  }
}

async function rotate() {
  rotating.value = true
  try {
    const response = await rotateIntakeKey()
    freshKey.value = response.data.key
    await load()
    toast.add({ title: t('leads.settings.rotate'), color: 'success' })
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.rotate')),
      color: 'error'
    })
  } finally {
    rotating.value = false
  }
}

async function toggleKey(value: boolean) {
  togglingKey.value = true
  try {
    const response = await setIntakeKeyActive(value)
    if (settings.value) settings.value = { ...settings.value, key: response.data }
  } catch (e: unknown) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('leads.errors.settingsSave')),
      color: 'error'
    })
  } finally {
    togglingKey.value = false
  }
}

async function copy(value: string | null | undefined) {
  if (!value || !import.meta.client) return
  try {
    await navigator.clipboard?.writeText(value)
    toast.add({ title: t('leads.settings.copied'), color: 'success' })
  } catch {
    // Clipboard access can be denied (insecure origin, browser policy).
    // Say so instead of silently showing a success the user cannot see.
    toast.add({ title: t('leads.errors.copy'), color: 'error' })
  }
}

function lastUsedLabel(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : t('leads.settings.never')
}
</script>

<template>
  <div class="space-y-6 max-w-3xl">
    <UAlert
      v-if="!canRead"
      color="warning"
      variant="soft"
      :title="t('leads.settings.noPermission')"
    />

    <template v-else>
      <div>
        <h2 class="text-h2 text-default">
          {{ t('leads.settings.title') }}
        </h2>
        <p class="text-body text-muted">
          {{ t('leads.settings.description') }}
        </p>
      </div>

      <USkeleton
        v-if="loading"
        class="h-64 w-full"
      />

      <template v-else-if="settings">
        <!-- 2. Today's gauge (read before the number behind it). -->
        <UCard>
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div class="text-caption text-subtle">
                {{ t('leads.settings.capLabel') }}
              </div>
              <div class="text-h1 text-default tnum">
                {{ gaugeLabel }}
              </div>
            </div>
          </div>
          <UAlert
            v-if="atLimit"
            class="mt-3"
            color="warning"
            variant="soft"
            icon="i-lucide-pause-circle"
            :title="t('leads.settings.atLimit')"
          />
          <p class="text-caption text-subtle mt-3">
            {{ t('leads.settings.capLoweredWarning') }}
          </p>
        </UCard>

        <!-- 1. The cap. -->
        <UCard>
          <template #header>
            <span class="text-ui font-medium text-default">{{ t('leads.settings.capLabel') }}</span>
          </template>
          <div class="flex flex-wrap items-end gap-3">
            <UFormField
              :label="t('leads.settings.capLabel')"
              :help="t('leads.settings.capHint')"
              class="w-40"
            >
              <!-- Read-only rather than hidden when the role cannot write:
                   the cap is the number behind what staff are seeing. -->
              <UInput
                v-model.number="capInput"
                type="number"
                min="0"
                :max="CAP_MAX"
                :disabled="!canWrite"
              />
            </UFormField>
            <UButton
              v-if="canWrite"
              :loading="savingCap"
              :disabled="!capValid"
              icon="i-lucide-save"
              @click="saveCap"
            >
              {{ t('leads.settings.capSave') }}
            </UButton>
          </div>
          <p
            v-if="!canWrite"
            class="text-caption text-subtle mt-3"
          >
            {{ t('leads.settings.readOnly') }}
          </p>
        </UCard>

        <!-- 3. The intake key. -->
        <UCard>
          <template #header>
            <div class="flex items-center justify-between gap-2">
              <span class="text-ui font-medium text-default">{{ t('leads.settings.keyTitle') }}</span>
              <UBadge
                v-if="settings.key.configured"
                :color="settings.key.is_active ? 'success' : 'warning'"
                variant="subtle"
              >
                {{ settings.key.is_active ? t('leads.settings.keyActive') : t('leads.settings.keyInactive') }}
              </UBadge>
            </div>
          </template>

          <div
            v-if="settings.key.configured"
            class="space-y-3"
          >
            <dl class="flex flex-wrap gap-x-6 gap-y-1 text-ui">
              <div>
                <dt class="text-caption text-subtle">
                  {{ t('leads.settings.keyPrefix') }}
                </dt>
                <dd
                  class="text-default font-mono"
                  dir="ltr"
                >
                  {{ settings.key.key_prefix }}…
                </dd>
              </div>
              <div>
                <dt class="text-caption text-subtle">
                  {{ t('leads.settings.lastUsed') }}
                </dt>
                <dd class="text-default">
                  {{ lastUsedLabel(settings.key.last_used_at) }}
                </dd>
              </div>
            </dl>

            <UFormField
              v-if="canWrite"
              :label="t('leads.settings.activate')"
            >
              <USwitch
                :model-value="settings.key.is_active"
                :disabled="togglingKey"
                @update:model-value="(value) => toggleKey(Boolean(value))"
              />
            </UFormField>
          </div>

          <p
            v-else
            class="text-body text-muted"
          >
            {{ t('leads.settings.keyMissing') }}
          </p>

          <template v-if="canWrite">
            <UButton
              class="mt-4"
              variant="outline"
              icon="i-lucide-key-round"
              :loading="rotating"
              @click="rotate"
            >
              {{ t('leads.settings.rotate') }}
            </UButton>
            <p class="text-caption text-subtle mt-2">
              {{ t('leads.settings.rotateWarning') }}
            </p>
          </template>
        </UCard>

        <!-- The freshly rotated key: shown once, kept only in local state. -->
        <UCard v-if="freshKey">
          <template #header>
            <span class="text-ui font-medium text-default">{{ t('leads.settings.keyTitle') }}</span>
          </template>
          <UAlert
            color="warning"
            variant="soft"
            icon="i-lucide-eye"
            :title="t('leads.settings.rotateCopyOnce')"
          />
          <div class="flex items-center gap-2 mt-3">
            <UInput
              :model-value="freshKey"
              readonly
              class="flex-1 font-mono"
              dir="ltr"
            />
            <UButton
              icon="i-lucide-copy"
              variant="outline"
              :aria-label="t('leads.settings.copy')"
              @click="copy(freshKey)"
            >
              {{ t('leads.settings.copy') }}
            </UButton>
          </div>
        </UCard>

        <!-- 4 + 5. URL and the snippet the clinic's web developer needs. -->
        <UCard>
          <template #header>
            <span class="text-ui font-medium text-default">{{ t('leads.settings.intakeUrl') }}</span>
          </template>
          <div class="flex items-center gap-2">
            <UInput
              :model-value="intakeUrl"
              readonly
              class="flex-1"
              dir="ltr"
            />
            <UButton
              icon="i-lucide-copy"
              variant="outline"
              :aria-label="t('leads.settings.copy')"
              @click="copy(intakeUrl)"
            >
              {{ t('leads.settings.copy') }}
            </UButton>
          </div>

          <div class="mt-4">
            <div class="flex items-center justify-between gap-2 mb-1">
              <div class="text-caption text-subtle">
                {{ t('leads.settings.example') }}
              </div>
              <UButton
                icon="i-lucide-copy"
                variant="ghost"
                color="neutral"
                size="xs"
                @click="copy(curlExample)"
              >
                {{ t('leads.settings.copy') }}
              </UButton>
            </div>
            <pre
              class="text-caption bg-surface-muted rounded-token-md p-3 overflow-x-auto whitespace-pre"
              dir="ltr"
            >{{ curlExample }}</pre>
          </div>

          <UAlert
            class="mt-4"
            color="info"
            variant="soft"
            icon="i-lucide-route"
            :description="t('leads.settings.routingNote')"
          />
        </UCard>
      </template>
    </template>
  </div>
</template>
