<script setup lang="ts">
// Empty-state starter chips. Each chip is gated by the same RBAC string the
// underlying capability uses, so a user only ever sees what they could do.
import { PERMISSIONS } from '~/config/permissions'

const { t } = useI18n()
const { can } = usePermissions()
const emit = defineEmits<{ pick: [prompt: string] }>()

type Category = 'workflows' | 'patients' | 'agenda' | 'recalls' | 'money' | 'reports'

interface Suggestion {
  id: string
  icon: string
  cat: Category
  permission: string
}

const ITEMS: Suggestion[] = [
  // Playbooks (multi-step recipes; gated by the first step's permission).
  { id: 'dailyBriefing', icon: 'i-lucide-sunrise', cat: 'workflows', permission: PERMISSIONS.appointments.read },
  { id: 'prepareVisit', icon: 'i-lucide-clipboard-list', cat: 'workflows', permission: PERMISSIONS.patients.read },
  { id: 'fillGap', icon: 'i-lucide-calendar-search', cat: 'workflows', permission: PERMISSIONS.recalls.read },
  { id: 'searchPatient', icon: 'i-lucide-search', cat: 'patients', permission: PERMISSIONS.patients.read },
  { id: 'patientSummary', icon: 'i-lucide-file-text', cat: 'patients', permission: PERMISSIONS.patients.read },
  { id: 'freeSlots', icon: 'i-lucide-calendar-clock', cat: 'agenda', permission: PERMISSIONS.appointments.read },
  { id: 'bookAppointment', icon: 'i-lucide-calendar-plus', cat: 'agenda', permission: PERMISSIONS.appointments.write },
  { id: 'dueRecalls', icon: 'i-lucide-phone-call', cat: 'recalls', permission: PERMISSIONS.recalls.read },
  { id: 'pendingBudgets', icon: 'i-lucide-file-clock', cat: 'money', permission: PERMISSIONS.budget.read },
  { id: 'recordPayment', icon: 'i-lucide-hand-coins', cat: 'money', permission: PERMISSIONS.payments.recordWrite },
  { id: 'monthCollections', icon: 'i-lucide-banknote', cat: 'reports', permission: PERMISSIONS.payments.reportsRead },
  { id: 'agendaSummary', icon: 'i-lucide-bar-chart-3', cat: 'reports', permission: PERMISSIONS.reports.schedulingRead }
]

const CATEGORIES: Category[] = ['workflows', 'patients', 'agenda', 'recalls', 'money', 'reports']

const groups = computed(() =>
  CATEGORIES.map(cat => ({
    cat,
    items: ITEMS.filter(s => s.cat === cat && can(s.permission))
  })).filter(g => g.items.length > 0)
)
</script>

<template>
  <div class="flex flex-col items-center gap-5 px-2 py-8 text-center">
    <UIcon
      name="i-lucide-sparkles"
      class="size-7 text-primary"
    />
    <p class="text-base font-medium">
      {{ t('copilot.suggest.heading') }}
    </p>

    <div class="flex w-full flex-col gap-4 text-left">
      <div
        v-for="g in groups"
        :key="g.cat"
        class="flex flex-col gap-2"
      >
        <p class="px-1 text-xs font-medium uppercase tracking-wide text-muted">
          {{ t(`copilot.suggest.cat.${g.cat}`) }}
        </p>
        <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <UButton
            v-for="s in g.items"
            :key="s.id"
            :icon="s.icon"
            color="neutral"
            variant="soft"
            size="sm"
            class="justify-start"
            @click="emit('pick', t(`copilot.suggest.prompt.${s.id}`))"
          >
            {{ t(`copilot.suggest.${s.id}`) }}
          </UButton>
        </div>
      </div>
    </div>
  </div>
</template>
