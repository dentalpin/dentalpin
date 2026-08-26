<script setup lang="ts">
import type { PipelineRow, PipelineTab } from '../../composables/usePipeline'
import type { UiColor } from '~~/app/config/severity'

const props = defineProps<{
  tab: PipelineTab
  q: string
}>()

const { t, locale } = useI18n()
const router = useRouter()
const toast = useToast()
const {
  rows,
  total,
  page,
  pageSize,
  loading,
  filters,
  fetchPipeline
} = usePipeline()

watch(
  () => props.tab,
  async (next) => {
    page.value = 1
    await fetchPipeline({ tab: next, page: 1, q: props.q || undefined })
  }
)

watch(
  () => props.q,
  async (val) => {
    filters.q = val || undefined
    page.value = 1
    await fetchPipeline({ tab: props.tab, page: 1, q: val || undefined })
  }
)

onMounted(async () => {
  filters.q = props.q || undefined
  await fetchPipeline({ tab: props.tab, page: 1, q: props.q || undefined })
})

function changePage(next: number) {
  page.value = next
  fetchPipeline({ tab: props.tab, page: next, q: props.q || undefined })
}

function patientName(row: PipelineRow): string {
  return `${row.patient.first_name} ${row.patient.last_name}`.trim()
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleDateString(locale.value, {
      day: '2-digit',
      month: 'short'
    })
  } catch {
    return iso
  }
}

function statusBadgeColor(status: string): UiColor {
  switch (status) {
    case 'draft':
      return 'neutral'
    case 'pending':
      return 'warning'
    case 'active':
      return 'success'
    case 'completed':
      return 'info'
    case 'closed':
      return 'error'
    case 'archived':
      return 'neutral'
    default:
      return 'neutral'
  }
}

function openPlan(row: PipelineRow) {
  router.push(`/treatment-plans/${row.plan_id}`)
}

function callPatient(row: PipelineRow) {
  if (!row.patient.phone) {
    toast.add({ title: t('pipeline.row.noBudget'), color: 'warning' })
    return
  }
  window.location.href = `tel:${row.patient.phone}`
}

function whatsappPatient(row: PipelineRow) {
  if (!row.patient.phone) return
  const phone = row.patient.phone.replace(/\D/g, '')
  window.open(`https://wa.me/${phone}`, '_blank', 'noopener')
}
</script>

<template>
  <div class="space-y-4">
    <div
      v-if="loading"
      class="rounded-md border border-dashed border-[var(--ui-border)] py-12 text-center text-sm text-[var(--ui-text-muted)]"
    >
      {{ t('pipeline.loading') }}
    </div>

    <div
      v-else-if="rows.length === 0"
      class="rounded-md border border-dashed border-[var(--ui-border)] py-12 text-center text-sm text-[var(--ui-text-muted)]"
    >
      {{ t('pipeline.empty') }}
    </div>

    <div
      v-else
      class="space-y-2"
    >
      <UCard
        v-for="row in rows"
        :key="row.plan_id"
        class="hover:border-[var(--ui-primary)] transition-colors"
      >
        <div class="flex flex-col md:flex-row md:items-center md:gap-4">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-3">
              <UAvatar
                :alt="patientName(row)"
                :text="patientName(row).slice(0, 2).toUpperCase()"
                size="md"
              />
              <div class="min-w-0">
                <button
                  type="button"
                  class="block text-left font-medium hover:underline truncate"
                  @click="openPlan(row)"
                >
                  {{ patientName(row) }}
                </button>
                <div class="text-xs text-[var(--ui-text-muted)] flex items-center gap-2">
                  <span>{{ row.plan_number }}</span>
                  <UBadge
                    :color="statusBadgeColor(row.plan_status)"
                    variant="soft"
                    size="xs"
                  >
                    {{ t(`treatmentPlans.status.${row.plan_status}`) }}
                  </UBadge>
                  <span v-if="row.closure_reason">
                    · {{ t(`treatmentPlans.closureReason.${row.closure_reason}`) }}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div class="hidden md:block text-xs text-[var(--ui-text-muted)] min-w-24">
            <div>{{ t('pipeline.row.items') }}</div>
            <div class="text-sm text-[var(--ui-text-toned)]">
              {{ row.items_completed }} / {{ row.items_total }}
            </div>
          </div>

          <div class="hidden md:block min-w-32 text-xs">
            <div class="text-[var(--ui-text-muted)]">
              {{ t('pipeline.row.budget') }}
            </div>
            <div
              v-if="row.budget"
              class="text-sm"
            >
              <UBadge
                :color="row.budget.status === 'expired' ? 'error' : 'neutral'"
                variant="soft"
                size="xs"
              >
                {{ row.budget.status }}
              </UBadge>
              <span
                v-if="row.budget.total !== null"
                class="ml-2"
              >
                {{ row.budget.total.toFixed(2) }} €
              </span>
            </div>
            <div
              v-else
              class="text-sm text-[var(--ui-text-muted)]"
            >
              {{ t('pipeline.row.noBudget') }}
            </div>
          </div>

          <div class="hidden md:block text-xs text-[var(--ui-text-muted)] min-w-24">
            <div>{{ t('pipeline.row.daysIn', { n: row.days_in_status }) }}</div>
            <div
              v-if="row.next_appointment"
              class="text-sm"
            >
              {{ t('pipeline.row.nextAppt') }}: {{ formatDate(row.next_appointment.start_at) }}
            </div>
            <div
              v-else
              class="text-sm text-[var(--ui-text-muted)]"
            >
              {{ t('pipeline.row.noNextAppt') }}
            </div>
          </div>

          <div class="flex items-center gap-2 mt-3 md:mt-0">
            <UButton
              v-if="row.patient.phone"
              icon="i-lucide-phone"
              :aria-label="t('pipeline.actions.call')"
              variant="ghost"
              color="neutral"
              size="sm"
              :title="t('pipeline.actions.call')"
              @click="callPatient(row)"
            />
            <UButton
              v-if="row.patient.phone"
              icon="i-lucide-message-circle"
              :aria-label="t('pipeline.actions.whatsapp')"
              variant="ghost"
              color="neutral"
              size="sm"
              :title="t('pipeline.actions.whatsapp')"
              @click="whatsappPatient(row)"
            />
            <UButton
              color="primary"
              variant="solid"
              size="sm"
              @click="openPlan(row)"
            >
              {{ t('pipeline.actions.open') }}
            </UButton>
          </div>
        </div>
      </UCard>
    </div>

    <div
      v-if="total > pageSize"
      class="flex justify-center"
    >
      <UPagination
        :model-value="page"
        :total="total"
        :page-count="pageSize"
        @update:model-value="changePage"
      />
    </div>
  </div>
</template>
