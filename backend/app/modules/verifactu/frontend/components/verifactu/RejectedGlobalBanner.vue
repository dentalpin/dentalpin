<script setup lang="ts">
// Global banner shown across the admin layout when at least one
// Verifactu record is rejected. Polls /verifactu/health every 60 s
// (cheap query) so the user sees the warning even on screens that
// don't otherwise touch verifactu data. /health needs
// verifactu.settings.read, so only roles holding it poll; anyone else
// would get an "Access denied" toast every minute (#1269).
import { PERMISSIONS } from '~~/app/config/permissions'

const { t } = useI18n()
const { health } = useVerifactu()
const { can } = usePermissions()

const rejectedCount = ref(0)
const showing = computed(() => rejectedCount.value > 0)
let timer: ReturnType<typeof setInterval> | null = null

async function refresh() {
  if (!can(PERMISSIONS.verifactu.settingsRead)) return
  try {
    const h = await health()
    rejectedCount.value = h.rejected_count ?? 0
  } catch {
    // Silent — module may not be installed for this clinic.
    rejectedCount.value = 0
  }
}

onMounted(() => {
  refresh()
  timer = setInterval(refresh, 60_000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <UAlert
    v-if="showing"
    color="error"
    variant="soft"
    icon="i-lucide-alert-octagon"
    :title="t('verifactu.globalBanner.title', { n: rejectedCount })"
    class="mb-4"
  >
    <template #description>
      <p class="mb-2">
        {{ t('verifactu.globalBanner.description') }}
      </p>
      <UButton
        to="/settings/verifactu/queue"
        color="primary"
        size="sm"
      >
        {{ t('verifactu.globalBanner.cta') }}
      </UButton>
    </template>
  </UAlert>
</template>
