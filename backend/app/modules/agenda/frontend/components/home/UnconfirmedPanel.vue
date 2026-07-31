<script setup lang="ts">
import type { Appointment } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail } from '~~/app/utils/error'

defineProps<{ ctx?: unknown }>()

const { t, locale } = useI18n()
const { can } = usePermissions()
const {
  tomorrowUnconfirmed,
  tomorrowLoaded,
  fetchTomorrowUnconfirmed,
  removeTomorrowUnconfirmed
} = useHomeAgenda()
const { transition } = useAppointments()
const toast = useToast()

const pending = computed(() => !tomorrowLoaded.value)
const canWrite = computed(() => can(PERMISSIONS.appointments.write))
const busyIds = ref<Set<string>>(new Set())

onMounted(() => {
  if (!tomorrowLoaded.value) fetchTomorrowUnconfirmed()
})
onActivated(() => {
  fetchTomorrowUnconfirmed()
})

async function confirm(a: Appointment) {
  if (!canWrite.value || busyIds.value.has(a.id)) return
  const next = new Set(busyIds.value)
  next.add(a.id)
  busyIds.value = next
  try {
    await transition(a.id, 'confirmed')
    removeTomorrowUnconfirmed(a.id)
  } catch (e) {
    toast.add({
      title: t('dashboard.unconfirmed.confirmError'),
      description: errorDetail(e),
      color: 'error'
    })
  } finally {
    const post = new Set(busyIds.value)
    post.delete(a.id)
    busyIds.value = post
  }
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' })
}

function isoDay(iso: string): string {
  const d = new Date(iso)
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function appointmentHref(a: Appointment): string {
  return `/appointments?highlight=${a.id}&date=${isoDay(a.start_time)}`
}
</script>

<template>
  <SectionCard
    icon="i-lucide-calendar-check"
    icon-role="warning"
    :title="t('dashboard.unconfirmed.title')"
  >
    <div
      v-if="pending"
      class="space-y-2"
    >
      <USkeleton class="h-10 w-full" />
      <USkeleton class="h-10 w-full" />
    </div>

    <EmptyState
      v-else-if="tomorrowUnconfirmed.length === 0"
      icon="i-lucide-check-check"
      :title="t('dashboard.unconfirmed.empty')"
    />

    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="a in tomorrowUnconfirmed"
        :key="a.id"
      >
        <ListRow :to="appointmentHref(a)">
          <template #leading>
            <span class="text-ui tnum text-default w-12">
              {{ formatTime(a.start_time) }}
            </span>
          </template>
          <template #title>
            {{ a.patient?.first_name }} {{ a.patient?.last_name }}
          </template>
          <template #subtitle>
            <span v-if="a.professional">
              {{ a.professional.first_name }} {{ a.professional.last_name }}
            </span>
            <span
              v-if="a.cabinet"
              class="ml-1 text-subtle"
            >
              · {{ a.cabinet }}
            </span>
          </template>
          <template
            v-if="canWrite"
            #actions
          >
            <UButton
              size="xs"
              variant="soft"
              color="primary"
              :loading="busyIds.has(a.id)"
              icon="i-lucide-check"
              @click.stop.prevent="confirm(a)"
            >
              {{ t('dashboard.unconfirmed.confirm') }}
            </UButton>
          </template>
        </ListRow>
      </li>
    </ul>
  </SectionCard>
</template>
