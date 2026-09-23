<script setup lang="ts">
/**
 * /orthodontics inbox: active / overdue / unscheduled / finished tabs,
 * case sheet inline. Deep-linkable via ?case_id=.
 */
import type { OrthoCase } from '../composables/useOrthodontics'
import { PERMISSIONS } from '~~/app/config/permissions'
import OrthoCaseSheet from '../components/OrthoCaseSheet.vue'

const { t, locale } = useI18n()
const { can } = usePermissions()
const route = useRoute()
const { listCases } = useOrthodontics()

const canRead = computed(() => can(PERMISSIONS.orthodontics.casesRead))

const tab = ref<'active' | 'overdue' | 'unscheduled' | 'finished'>('active')
const rows = ref<OrthoCase[]>([])
const selectedId = ref<string | null>((route.query.case_id as string) || null)
const isLoading = ref(false)

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  return new Intl.DateTimeFormat(locale.value, { dateStyle: 'medium' }).format(new Date(iso))
}

function isOverdue(c: OrthoCase): boolean {
  if (!c.next_due || c.status === 'finished' || c.status === 'transferred_out') return false
  return new Date(c.next_due) < new Date(new Date().toDateString())
}

const filtered = computed(() => {
  switch (tab.value) {
    case 'active':
      return rows.value.filter(c => c.status === 'active' || c.status === 'paused')
    case 'overdue':
      return rows.value.filter(isOverdue)
    case 'unscheduled':
      return rows.value.filter(c => !c.next_due && (c.status === 'active' || c.status === 'paused'))
    case 'finished':
      return rows.value.filter(c => c.status === 'finished' || c.status === 'transferred_out')
  }
  return rows.value
})

async function refresh() {
  isLoading.value = true
  try {
    rows.value = await listCases()
  } finally {
    isLoading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div
    v-if="canRead"
    class="p-4"
  >
    <h1 class="mb-3 text-xl font-semibold">
      {{ t('orthodontics.inbox.title') }}
    </h1>
    <div class="grid gap-4 md:grid-cols-[320px_1fr]">
      <div>
        <div class="mb-2 flex flex-wrap gap-1">
          <UButton
            v-for="k in (['active', 'overdue', 'unscheduled', 'finished'] as const)"
            :key="k"
            size="sm"
            :variant="tab === k ? 'solid' : 'soft'"
            @click="tab = k; selectedId = null"
          >
            {{ t(`orthodontics.inbox.${k}`) }}
          </UButton>
        </div>
        <USkeleton
          v-if="isLoading"
          class="h-24"
        />
        <p
          v-else-if="filtered.length === 0"
          class="text-sm text-gray-500"
        >
          {{ t('orthodontics.inbox.empty') }}
        </p>
        <UCard
          v-for="c in filtered"
          :key="c.id"
          class="mb-2 cursor-pointer"
          :class="{ 'ring-2': selectedId === c.id }"
          @click="selectedId = c.id"
        >
          <div class="text-sm font-medium">
            {{ t(`orthodontics.appliance.${c.appliance_type}`) }}
          </div>
          <div class="text-xs text-gray-500">
            {{ t(`orthodontics.status.${c.status}`) }}
            <span v-if="c.next_due">· {{ t('orthodontics.inbox.nextDue') }}: {{ formatDate(c.next_due) }}</span>
          </div>
        </UCard>
      </div>
      <div>
        <OrthoCaseSheet
          v-if="selectedId"
          :key="selectedId"
          :case-id="selectedId"
        />
      </div>
    </div>
  </div>
</template>
