<script setup lang="ts">
import type { TreatmentPlan, TreatmentPlanStatus } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'

const props = defineProps<{
  q: string
}>()

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const { can } = usePermissions()
const {
  plans,
  total,
  loading,
  fetchPlans,
  deletePlan,
} = useTreatmentPlans()

const selectedStatuses = ref<TreatmentPlanStatus[]>([])
const currentPage = ref(1)
const pageSize = 20

const statusOptions = computed(() => [
  { label: t('treatmentPlans.status.draft'), value: 'draft' as TreatmentPlanStatus },
  { label: t('treatmentPlans.status.pending'), value: 'pending' as TreatmentPlanStatus },
  { label: t('treatmentPlans.status.active'), value: 'active' as TreatmentPlanStatus },
  { label: t('treatmentPlans.status.completed'), value: 'completed' as TreatmentPlanStatus },
  { label: t('treatmentPlans.status.closed'), value: 'closed' as TreatmentPlanStatus },
  { label: t('treatmentPlans.status.archived'), value: 'archived' as TreatmentPlanStatus },
])

async function loadPlans() {
  await fetchPlans({
    page: currentPage.value,
    page_size: pageSize,
    search: props.q || undefined,
    status: selectedStatuses.value.length > 0 ? selectedStatuses.value : undefined,
  })
}

onMounted(() => {
  loadPlans()
})

watch(
  () => props.q,
  () => {
    currentPage.value = 1
    loadPlans()
  }
)

watch([currentPage, selectedStatuses], () => {
  loadPlans()
})

const totalPages = computed(() => Math.ceil(total.value / pageSize))

function createPlan() {
  router.push('/treatment-plans/new')
}

async function handleDelete(plan: TreatmentPlan, event: Event) {
  event.stopPropagation()
  if (!confirm(t('treatmentPlans.confirmations.delete'))) return

  try {
    await deletePlan(plan.id)
    toast.add({
      title: t('common.success'),
      description: t('treatmentPlans.messages.deleted'),
      color: 'success',
    })
  } catch (e) {
    toast.add({
      title: t('common.error'),
      description: errorMessage(e, t('treatmentPlans.errors.delete')),
      color: 'error',
    })
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(locale.value)
}

function getPatientName(plan: TreatmentPlan): string {
  if (!plan.patient) return '-'
  return `${plan.patient.last_name}, ${plan.patient.first_name}`
}

function getItemCount(plan: TreatmentPlan): number {
  return plan.item_count || 0
}
</script>

<template>
  <div>
    <div class="flex flex-wrap gap-[var(--density-gap,0.75rem)] mb-[var(--density-gap,1rem)]">
      <USelectMenu
        v-model="selectedStatuses"
        :items="statusOptions"
        value-key="value"
        multiple
        :placeholder="t('treatmentPlans.filters.allStatuses')"
        class="w-64"
      />
    </div>

    <UCard>
      <div
        v-if="loading"
        class="space-y-3"
      >
        <USkeleton
          v-for="i in 5"
          :key="i"
          class="h-16 w-full"
        />
      </div>

      <EmptyState
        v-else-if="plans.length === 0"
        icon="i-lucide-clipboard-list"
        :title="props.q || selectedStatuses.length > 0 ? t('treatmentPlans.noItems') : t('treatmentPlans.empty')"
      >
        <template
          v-if="!props.q && selectedStatuses.length === 0 && can(PERMISSIONS.treatmentPlans.write)"
          #actions
        >
          <UButton
            color="primary"
            variant="soft"
            icon="i-lucide-plus"
            @click="createPlan"
          >
            {{ t('treatmentPlans.emptyAction') }}
          </UButton>
        </template>
      </EmptyState>

      <div
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <ListRow
          v-for="plan in plans"
          :key="plan.id"
          :to="`/treatment-plans/${plan.id}`"
        >
          <template #title>
            <span class="tnum">{{ plan.plan_number }}</span>
            <TreatmentPlanStatusBadge :status="plan.status" />
            <span class="text-default truncate">
              {{ plan.title || t('treatmentPlans.untitled') }}
            </span>
          </template>
          <template #subtitle>
            {{ getPatientName(plan) }}
          </template>
          <template #meta>
            <span class="hidden sm:inline text-caption text-subtle tnum">
              {{ t('treatmentPlans.itemCount', { count: getItemCount(plan) }, getItemCount(plan)) }}
            </span>
            <span class="hidden sm:inline text-caption text-subtle tnum">
              {{ formatDate(plan.created_at) }}
            </span>
          </template>
          <template
            v-if="can(PERMISSIONS.treatmentPlans.write) && plan.status === 'draft'"
            #actions
          >
            <UButton
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              size="xs"
              :aria-label="t('treatmentPlans.delete')"
              :title="t('treatmentPlans.delete')"
              @click="handleDelete(plan, $event)"
            />
          </template>
        </ListRow>
      </div>

      <PaginationBar
        v-model:page="currentPage"
        :total-pages="totalPages"
      />
    </UCard>
  </div>
</template>
