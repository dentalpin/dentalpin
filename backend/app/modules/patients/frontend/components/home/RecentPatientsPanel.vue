<script setup lang="ts">
import type { Patient, ApiResponse } from '~~/app/types'

defineProps<{ ctx?: unknown }>()

const { t, locale } = useI18n()
const api = useApi()

const patients = ref<Patient[]>([])
const pending = ref(true)

async function load() {
  try {
    const res = await api.get<ApiResponse<Patient[]>>('/api/v1/patients/recent?limit=6')
    patients.value = res.data
  } catch {
    patients.value = []
  } finally {
    pending.value = false
  }
}

onMounted(load)
onActivated(load)

function initials(p: Patient): string {
  return [p.first_name?.[0], p.last_name?.[0]].filter(Boolean).join('').toUpperCase() || '?'
}

function relative(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diffDays = Math.round((now - then) / 86_400_000)
  const rtf = new Intl.RelativeTimeFormat(locale.value, { numeric: 'auto' })
  if (diffDays < 1) return rtf.format(-Math.round((now - then) / 3_600_000), 'hour')
  if (diffDays < 30) return rtf.format(-diffDays, 'day')
  return new Date(iso).toLocaleDateString(locale.value, { day: 'numeric', month: 'short' })
}
</script>

<template>
  <SectionCard
    icon="i-lucide-users"
    icon-role="info"
    :title="t('dashboard.recent.title')"
  >
    <template #actions>
      <UButton
        to="/patients"
        variant="ghost"
        color="neutral"
        size="xs"
        trailing-icon="i-lucide-arrow-right"
        :aria-label="t('nav.patients')"
      />
    </template>

    <div
      v-if="pending"
      class="space-y-2"
    >
      <USkeleton
        v-for="i in 3"
        :key="i"
        class="h-10 w-full"
      />
    </div>

    <EmptyState
      v-else-if="patients.length === 0"
      icon="i-lucide-users"
      :title="t('dashboard.recent.empty')"
    />

    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="p in patients"
        :key="p.id"
      >
        <ListRow :to="`/patients/${p.id}`">
          <template #leading>
            <UAvatar
              :alt="`${p.first_name} ${p.last_name}`"
              :text="initials(p)"
              size="sm"
            />
          </template>
          <template #title>
            {{ p.first_name }} {{ p.last_name }}
          </template>
          <template #subtitle>
            {{ p.phone || p.email || '—' }}
          </template>
          <template #meta>
            <span class="text-caption text-subtle tnum">
              {{ relative(p.created_at) }}
            </span>
          </template>
        </ListRow>
      </li>
    </ul>
  </SectionCard>
</template>
