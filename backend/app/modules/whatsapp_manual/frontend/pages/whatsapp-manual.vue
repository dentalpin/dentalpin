<script setup lang="ts">
import { errorDetail } from '~~/app/utils/error'
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  MANUAL_WHATSAPP_PATH,
  useManualWhatsApp
} from '../composables/useManualWhatsApp'
import type { ManualWhatsAppTray } from '../composables/useManualWhatsApp'

definePageMeta({ middleware: ['auth'] })

const { t, locale } = useI18n()
const { can } = usePermissions()
const api = useManualWhatsApp()
const toast = useToast()
const badges = useNavigationBadges()
const { currentClinic } = useClinicState()
const tray = ref<ManualWhatsAppTray | null>(null)
const page = ref(1)
const selected = ref<string[]>([])
const loading = ref(true)
const busy = ref(false)
const failed = ref(false)
const configureOpen = ref(false)
const canWrite = computed(() => can(PERMISSIONS.whatsappManual.write))
const dateFormatter = computed(() => new Intl.DateTimeFormat(locale.value, {
  dateStyle: 'medium',
  timeStyle: 'short',
  timeZone: currentClinic.value?.timezone
}))

if (!can(PERMISSIONS.whatsappManual.read)) {
  await navigateTo('/')
}

async function load(showLoading = true) {
  if (showLoading) loading.value = true
  try {
    const result = (await api.tray(page.value)).data
    const last = Math.max(1, Math.ceil(result.total / 25))
    if (page.value > last) {
      page.value = last
      return
    }
    tray.value = result
    badges.value[MANUAL_WHATSAPP_PATH] = result.total
    const visible = new Set(result.items.map(row => row.id))
    selected.value = selected.value.filter(id => visible.has(id))
    failed.value = false
  } catch {
    if (showLoading) failed.value = true
  } finally {
    loading.value = false
  }
}

let refreshTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  void load()
  refreshTimer = setInterval(() => {
    if (!busy.value && !loading.value && !failed.value) void load(false)
  }, 15_000)
})
onUnmounted(() => clearInterval(refreshTimer))
watch(page, () => {
  selected.value = []
  void load()
})

function toggle(id: string, checked: boolean | 'indeterminate') {
  selected.value = checked === true
    ? [...selected.value, id]
    : selected.value.filter(value => value !== id)
}

async function openDraft(id: string) {
  if (busy.value) return
  const popup = window.open('about:blank', '_blank')
  if (popup) popup.opener = null
  busy.value = true
  try {
    const { data: url } = await api.open(id)
    if (popup) popup.location.replace(url)
    else window.location.assign(url)
  } catch (error: unknown) {
    popup?.close()
    const reason = errorDetail(error)
    const key = reason === 'appointment_changed' || reason === 'appointment_expired'
      ? 'whatsapp_manual.appointmentChanged'
      : 'whatsapp_manual.openError'
    toast.add({ title: t(key), color: 'error' })
    await load()
  } finally {
    busy.value = false
  }
}

async function apply(action: 'mark_sent' | 'dismiss', ids: string[]) {
  if (busy.value || !ids.length) return
  busy.value = true
  try {
    await api.action(action, ids)
    toast.add({
      title: t(action === 'mark_sent' ? 'whatsapp_manual.marked' : 'whatsapp_manual.dismissed'),
      color: 'success'
    })
  } catch {
    toast.add({ title: t('whatsapp_manual.actionError'), color: 'error' })
  } finally {
    await load()
    busy.value = false
  }
}

async function configure(enabled: boolean) {
  busy.value = true
  try {
    await api.configure(enabled)
    configureOpen.value = false
    await load()
  } catch {
    toast.add({ title: t('whatsapp_manual.configError'), color: 'error' })
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="mx-auto max-w-5xl space-y-5 p-4 sm:p-6">
    <header class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 class="text-h1 text-default">
          {{ t('whatsapp_manual.title') }}
        </h1>
        <p class="mt-1 text-sm text-muted">
          {{ t('whatsapp_manual.subtitle') }}
        </p>
      </div>
      <UButton
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        :label="t('whatsapp_manual.refresh')"
        :disabled="loading || busy"
        @click="load()"
      />
    </header>

    <UAlert
      v-if="tray && !tray.enabled"
      color="warning"
      variant="soft"
      icon="i-lucide-settings"
      :title="t('whatsapp_manual.disabled')"
    >
      <template
        v-if="can(PERMISSIONS.whatsappManual.settingsWrite)"
        #actions
      >
        <UModal
          v-model:open="configureOpen"
          :title="t('whatsapp_manual.enable')"
          :description="t('whatsapp_manual.enableHelp')"
        >
          <UButton
            color="neutral"
            variant="outline"
            :label="t('whatsapp_manual.enable')"
          />
          <template #footer>
            <UButton
              :label="t('whatsapp_manual.enable')"
              :loading="busy"
              @click="configure(true)"
            />
          </template>
        </UModal>
      </template>
    </UAlert>
    <UAlert
      color="info"
      variant="soft"
      icon="i-lucide-info"
      :description="t('whatsapp_manual.instructions')"
    />

    <USkeleton
      v-if="loading && !tray"
      class="h-32"
    />
    <UAlert
      v-else-if="failed"
      color="error"
      variant="soft"
      :title="t('whatsapp_manual.loadError')"
    />
    <section
      v-else-if="tray"
      class="space-y-3"
    >
      <div class="flex min-h-9 flex-wrap items-center justify-between gap-2">
        <p
          class="text-sm font-medium text-muted"
          aria-live="polite"
        >
          {{ t('whatsapp_manual.pending', tray.total) }}
          <span v-if="selected.length"> · {{ t('whatsapp_manual.selected', selected.length) }}</span>
        </p>
        <UButton
          v-if="canWrite && selected.length"
          :label="t('whatsapp_manual.markSelected')"
          icon="i-lucide-check-check"
          :disabled="busy"
          @click="apply('mark_sent', selected)"
        />
      </div>

      <UCard v-if="!tray.items.length">
        <div class="space-y-2 py-6 text-center">
          <UIcon
            name="i-lucide-inbox"
            class="size-7 text-muted"
          />
          <h2 class="font-medium text-default">
            {{ t('whatsapp_manual.empty') }}
          </h2>
          <p class="text-sm text-muted">
            {{ t('whatsapp_manual.emptyDetail') }}
          </p>
        </div>
      </UCard>

      <ul
        v-else
        class="space-y-3"
      >
        <li
          v-for="row in tray.items"
          :key="row.id"
        >
          <UCard variant="outline">
            <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div class="flex min-w-0 items-start gap-3">
                <UCheckbox
                  v-if="canWrite"
                  class="mt-0.5 shrink-0"
                  :aria-label="t('whatsapp_manual.select', { name: row.patient_name || row.phone })"
                  :model-value="selected.includes(row.id)"
                  :disabled="busy"
                  @update:model-value="toggle(row.id, $event)"
                />
                <div class="min-w-0 space-y-1">
                  <h2 class="font-semibold text-default">
                    {{ row.patient_name || t('whatsapp_manual.unknownPatient') }}
                  </h2>
                  <p class="flex flex-wrap gap-x-3 text-xs text-muted">
                    <span>{{ row.phone }}</span>
                    <span v-if="row.appointment_start_at">
                      {{ t('whatsapp_manual.appointment') }} · {{ dateFormatter.format(new Date(row.appointment_start_at)) }}
                    </span>
                  </p>
                  <p class="whitespace-pre-wrap break-words text-sm text-default">
                    {{ row.text }}
                  </p>
                </div>
              </div>
              <div
                v-if="canWrite"
                class="flex shrink-0 flex-wrap items-center gap-1"
              >
                <UButton
                  size="sm"
                  variant="soft"
                  icon="i-lucide-external-link"
                  :label="t('whatsapp_manual.open')"
                  :disabled="busy"
                  @click="openDraft(row.id)"
                />
                <UButton
                  color="neutral"
                  size="sm"
                  variant="ghost"
                  icon="i-lucide-check"
                  :label="t('whatsapp_manual.markSent')"
                  :disabled="busy"
                  @click="apply('mark_sent', [row.id])"
                />
                <UButton
                  color="neutral"
                  size="sm"
                  variant="ghost"
                  icon="i-lucide-x"
                  :label="t('whatsapp_manual.dismiss')"
                  :disabled="busy"
                  @click="apply('dismiss', [row.id])"
                />
              </div>
            </div>
          </UCard>
        </li>
      </ul>

      <UPagination
        v-if="tray.total > 25"
        v-model:page="page"
        :total="tray.total"
        :items-per-page="25"
      />
    </section>

    <UButton
      v-if="tray?.enabled && can(PERMISSIONS.whatsappManual.settingsWrite)"
      color="neutral"
      variant="ghost"
      size="sm"
      :disabled="busy"
      :label="t('whatsapp_manual.disable')"
      @click="configure(false)"
    />
  </div>
</template>
