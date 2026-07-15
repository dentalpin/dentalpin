<script setup lang="ts">
import type { ModuleInfo } from '~/types'
import { PERMISSIONS } from '~/config/permissions'

const { t } = useI18n()
const toast = useToast()
const { can } = usePermissions()
const modulesNav = useModules()

const admin = useModuleAdmin()

const canRead = computed(() => can(PERMISSIONS.admin.clinicRead))
const canWrite = computed(() => can(PERMISSIONS.admin.clinicWrite))

// Modal state.
type ConfirmVariant = 'install' | 'uninstall' | 'upgrade' | 'apply'
const showConfirm = ref(false)
const confirmVariant = ref<ConfirmVariant>('install')
const confirmTargetName = ref<string | undefined>(undefined)
const confirmScheduled = ref<string[]>([])
const confirmLoading = ref(false)
const confirmError = ref<string | null>(null)
const confirmForceAvailable = ref(false)

const showDetail = ref(false)
const detailModule = ref<ModuleInfo | null>(null)

const restarting = ref(false)

const pendingModules = computed(() =>
  admin.modules.value.filter(m =>
    ['to_install', 'to_upgrade', 'to_remove'].includes(m.state)
  )
)

const hasDoctorIssues = computed(() => admin.doctor.value?.ok === false)

onMounted(async () => {
  if (!canRead.value) {
    return
  }
  try {
    await admin.refresh()
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }, message?: string }
    toast.add({
      title: t('common.error'),
      description: e?.data?.detail ?? e?.message ?? t('common.networkError'),
      color: 'error'
    })
  }
})

function openInstallConfirm(name: string) {
  confirmVariant.value = 'install'
  confirmTargetName.value = name
  confirmScheduled.value = computeInstallPreview(name)
  confirmError.value = null
  confirmForceAvailable.value = false
  showConfirm.value = true
}

function openUninstallConfirm(name: string) {
  confirmVariant.value = 'uninstall'
  confirmTargetName.value = name
  confirmScheduled.value = []
  confirmError.value = null
  confirmForceAvailable.value = false
  showConfirm.value = true
}

function openUpgradeConfirm(name: string) {
  confirmVariant.value = 'upgrade'
  confirmTargetName.value = name
  confirmScheduled.value = []
  confirmError.value = null
  confirmForceAvailable.value = false
  showConfirm.value = true
}

function openApplyConfirm() {
  confirmVariant.value = 'apply'
  confirmTargetName.value = undefined
  confirmScheduled.value = pendingModules.value.map(m => m.name)
  confirmError.value = null
  confirmForceAvailable.value = false
  showConfirm.value = true
}

function viewDetails(name: string) {
  const module = admin.modules.value.find(m => m.name === name)
  if (!module) {
    return
  }
  detailModule.value = module
  showDetail.value = true
}

async function onConfirm(force: boolean) {
  const name = confirmTargetName.value
  confirmLoading.value = true
  confirmError.value = null
  try {
    if (confirmVariant.value === 'install' && name) {
      await admin.install(name, force)
      toast.add({
        title: t('settings.modules.toasts.scheduled'),
        color: 'success'
      })
      showConfirm.value = false
    } else if (confirmVariant.value === 'uninstall' && name) {
      await admin.uninstall(name, force)
      toast.add({
        title: t('settings.modules.toasts.scheduled'),
        color: 'success'
      })
      showConfirm.value = false
    } else if (confirmVariant.value === 'upgrade' && name) {
      await admin.upgrade(name)
      toast.add({
        title: t('settings.modules.toasts.scheduled'),
        color: 'success'
      })
      showConfirm.value = false
    } else if (confirmVariant.value === 'apply') {
      await runApply()
      showConfirm.value = false
    }
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }, message?: string }
    const detail = e?.data?.detail ?? e?.message ?? t('common.error')
    confirmError.value = detail
    // If uninstall was blocked by reverse-deps or removable=false, offer force.
    if (
      confirmVariant.value === 'uninstall'
      && /required by|removable=False/.test(detail)
    ) {
      confirmForceAvailable.value = true
    }
  } finally {
    confirmLoading.value = false
  }
}

async function runApply() {
  restarting.value = true
  try {
    await admin.restart()
    await admin.pollUntilSettled()
    await admin.refresh()
    await modulesNav.ensureLoaded(true)
    const erroredCount = admin.status.value?.errored.length ?? 0
    if (erroredCount > 0) {
      toast.add({
        title: t('settings.modules.restart.failed'),
        description: (admin.status.value?.errored ?? []).join(', '),
        color: 'error'
      })
    } else {
      toast.add({
        title: t('settings.modules.toasts.applied'),
        color: 'success'
      })
    }
  } catch (err: unknown) {
    const e = err as { data?: { detail?: string }, message?: string }
    const msg = e?.message === 'restart-timeout'
      ? t('settings.modules.restart.timeout')
      : (e?.data?.detail ?? e?.message ?? t('settings.modules.restart.failed'))
    toast.add({
      title: t('settings.modules.restart.failed'),
      description: msg,
      color: 'error'
    })
  } finally {
    restarting.value = false
  }
}

// Rough install preview: module + every uninstalled dep recursively. The
// authoritative chain is computed server-side and returned in `scheduled`
// after the install call; this is only for the confirmation modal.
function computeInstallPreview(name: string): string[] {
  const byName = new Map(admin.modules.value.map(m => [m.name, m]))
  const seen = new Set<string>()
  const out: string[] = []
  function visit(current: string) {
    if (seen.has(current)) {
      return
    }
    seen.add(current)
    const module = byName.get(current)
    if (!module) {
      return
    }
    for (const dep of module.depends) {
      const depModule = byName.get(dep)
      if (depModule && depModule.state !== 'installed') {
        visit(dep)
      }
    }
    out.push(current)
  }
  visit(name)
  return out
}
</script>

<template>
  <div class="space-y-6">
    <div class="flex items-center gap-3">
      <UButton
        to="/settings"
        variant="ghost"
        size="sm"
        icon="i-lucide-arrow-left"
      >
        {{ t('settings.title') }}
      </UButton>
    </div>

    <div>
      <h1 class="text-display text-default">
        {{ t('settings.modules.title') }}
      </h1>
      <p class="text-muted mt-1">
        {{ t('settings.modules.subtitle') }}
      </p>
    </div>

    <div
      v-if="!canRead"
      class="rounded-md border border-default p-6 text-sm text-muted"
    >
      {{ t('common.forbidden', 'Acceso denegado') }}
    </div>

    <template v-else>
      <!-- Doctor banner -->
      <ModuleDoctorBanner
        v-if="hasDoctorIssues && admin.doctor.value"
        :report="admin.doctor.value"
      />

      <!-- Pending changes banner -->
      <div
        v-if="pendingModules.length > 0"
        class="rounded-md border border-[var(--color-info-soft)] bg-[var(--color-info-soft)] px-4 py-3 flex items-center justify-between gap-3 flex-wrap"
      >
        <div class="text-sm">
          <span class="font-semibold">
            {{ t('settings.modules.pending.banner') }}
          </span>
          <span class="ml-1 text-subtle">
            {{ pendingModules.map(m => m.name).join(', ') }}
          </span>
        </div>
        <UButton
          v-if="canWrite"
          color="primary"
          icon="i-lucide-play"
          :loading="restarting"
          @click="openApplyConfirm"
        >
          {{ t('settings.modules.pending.apply') }}
        </UButton>
      </div>

      <!-- Loading skeleton -->
      <div
        v-if="admin.loading.value && admin.modules.value.length === 0"
        class="space-y-3"
      >
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
        <USkeleton class="h-24 w-full" />
      </div>

      <!-- Error state -->
      <UAlert
        v-else-if="admin.error.value && admin.modules.value.length === 0"
        color="error"
        icon="i-lucide-x-circle"
        :title="t('common.error')"
        :description="admin.error.value"
        :actions="[{ label: t('common.retry'), onClick: () => admin.refresh() }]"
      />

      <!-- Module list -->
      <div
        v-else
        class="space-y-3"
      >
        <ModuleCard
          v-for="module in admin.modules.value"
          :key="module.name"
          :module="module"
          :can-write="canWrite"
          @install="openInstallConfirm"
          @uninstall="openUninstallConfirm"
          @upgrade="openUpgradeConfirm"
          @view-details="viewDetails"
        />
      </div>
    </template>

    <!-- Confirmation modal -->
    <ModuleConfirmModal
      v-model:open="showConfirm"
      :variant="confirmVariant"
      :module-name="confirmTargetName"
      :scheduled="confirmScheduled"
      :loading="confirmLoading"
      :error="confirmError"
      :force-available="confirmForceAvailable"
      @confirm="onConfirm"
    />

    <!-- Detail modal -->
    <ModuleDetailModal
      v-model:open="showDetail"
      :module="detailModule"
    />

    <!-- Restart overlay -->
    <div
      v-if="restarting"
      class="fixed inset-0 z-50 flex items-center justify-center bg-[var(--color-bg-muted)]/80 backdrop-blur-sm"
    >
      <div class="rounded-md border border-default bg-[var(--color-bg-surface)] p-6 flex items-center gap-3">
        <UIcon
          name="i-lucide-loader-2"
          class="w-6 h-6 animate-spin text-primary-accent"
        />
        <span class="text-default">{{ t('settings.modules.restart.inProgress') }}</span>
      </div>
    </div>
  </div>
</template>
