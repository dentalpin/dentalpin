<script setup lang="ts">
import { toISODate } from '~~/app/utils/wallClock'

const { t } = useI18n()
const { can } = usePermissions()
const { fetchTreatmentPlanConversion, fetchFailed, resetFetchFailed } = useReports()
const today = new Date()
const firstDay = new Date(today.getFullYear(), today.getMonth(), 1)
const dateFrom = ref(toISODate(firstDay))
const dateTo = ref(toISODate(today))
const isLoading = ref(false)
const data = ref<Awaited<ReturnType<typeof fetchTreatmentPlanConversion>>>(null)
const canRead = computed(() => can('reports.scheduling.read'))

async function load() {
  if (!canRead.value || dateTo.value < dateFrom.value) return
  isLoading.value = true
  resetFetchFailed()
  try {
    data.value = await fetchTreatmentPlanConversion(dateFrom.value, dateTo.value)
  } finally {
    isLoading.value = false
  }
}

watch([dateFrom, dateTo], () => void load())
onMounted(() => void load())

function percent(value: number) {
  return new Intl.NumberFormat(undefined, { style: 'percent', maximumFractionDigits: 1 }).format(value)
}
</script>

<template>
  <div class="space-y-6">
    <header class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 class="text-display text-default">
          {{ t('reports.planConversion.title', 'Конверсия планов лечения') }}
        </h1>
        <p class="mt-1 max-w-2xl text-sm text-muted">
          {{ t('reports.planConversion.subtitle', 'Отслеживайте подтверждённые врачом планы: переход к записи и завершение лечения.') }}
        </p>
      </div>
      <div class="grid grid-cols-2 gap-2">
        <UFormField :label="t('reports.dashboard.periodFrom', 'С')">
          <UInput
            v-model="dateFrom"
            type="date"
          />
        </UFormField>
        <UFormField :label="t('reports.dashboard.periodTo', 'По')">
          <UInput
            v-model="dateTo"
            type="date"
          />
        </UFormField>
      </div>
    </header>

    <UAlert
      v-if="!canRead"
      icon="i-lucide-lock"
      color="warning"
      :title="t('reports.noAccess')"
    />
    <UAlert
      v-else-if="fetchFailed"
      icon="i-lucide-triangle-alert"
      color="error"
      :title="t('reports.loadError')"
      :actions="[{ label: t('common.retry'), onClick: () => load() }]"
    />
    <USkeleton
      v-else-if="isLoading"
      class="h-36 w-full"
    />
    <template v-else-if="data">
      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <UCard>
          <p class="text-sm text-muted">
            {{ t('reports.planConversion.confirmed', 'Планов подтверждено') }}
          </p>
          <p class="mt-2 text-3xl font-semibold tabular-nums">
            {{ data.confirmed_plans }}
          </p>
          <p class="mt-1 text-xs text-muted">
            {{ t('reports.planConversion.cohortHint', 'Когорта по дате подтверждения плана врачом') }}
          </p>
        </UCard>
        <UCard>
          <p class="text-sm text-muted">
            {{ t('reports.planConversion.booked', 'Записаны по плану') }}
          </p>
          <p class="mt-2 text-3xl font-semibold tabular-nums">
            {{ data.booked_plans }}
          </p>
          <p class="mt-1 text-xs text-muted">
            {{ percent(data.booking_conversion_rate) }} {{ t('reports.planConversion.ofPlans', 'от подтверждённых планов') }}
          </p>
        </UCard>
        <UCard>
          <p class="text-sm text-muted">
            {{ t('reports.planConversion.completedPlans', 'Планы лечения завершены') }}
          </p>
          <p class="mt-2 text-3xl font-semibold tabular-nums">
            {{ data.completed_plans }}
          </p>
          <p class="mt-1 text-xs text-muted">
            {{ percent(data.plan_completion_rate) }} {{ t('reports.planConversion.ofPlans', 'от подтверждённых планов') }}
          </p>
        </UCard>
      </section>

      <UCard>
        <template #header>
          <h2 class="font-semibold">
            {{ t('reports.planConversion.itemProgress', 'Выполнение пунктов лечения') }}
          </h2>
        </template>
        <div class="flex flex-wrap items-baseline justify-between gap-3">
          <p class="text-2xl font-semibold tabular-nums">
            {{ data.items_completed }} <span class="text-base font-normal text-muted">/ {{ data.items_total }}</span>
          </p>
          <p class="text-lg font-medium">
            {{ percent(data.item_completion_rate) }}
          </p>
        </div>
        <UProgress
          class="mt-4"
          :model-value="data.item_completion_rate * 100"
        />
        <p class="mt-3 text-sm text-muted">
          {{ t('reports.planConversion.metricNote', 'Запись учитывается, если пункт плана связан хотя бы с одной незакрытой записью. Выполнение считается по отметкам о завершении пунктов плана.') }}
        </p>
      </UCard>
    </template>
  </div>
</template>
