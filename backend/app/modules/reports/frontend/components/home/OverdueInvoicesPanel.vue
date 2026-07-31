<script setup lang="ts">
defineProps<{ ctx?: unknown }>()

const { t } = useI18n()
const { overdue, overdueLoaded, loadOverdue } = useHomeReports()

const pending = computed(() => !overdueLoaded.value)

onMounted(() => {
  if (!overdueLoaded.value) loadOverdue()
})
onActivated(() => {
  loadOverdue()
})

const topFive = computed(() => overdue.value.slice(0, 5))

const { format: formatMoney } = useCurrency()
</script>

<template>
  <SectionCard
    icon="i-lucide-alert-triangle"
    icon-role="danger"
    :title="t('dashboard.overdue.title')"
  >
    <template
      v-if="!pending && overdue.length > 0"
      #actions
    >
      <UButton
        to="/invoices?filter=overdue"
        variant="ghost"
        color="neutral"
        size="xs"
        trailing-icon="i-lucide-arrow-right"
      >
        {{ t('dashboard.overdue.viewAll') }}
      </UButton>
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
      v-else-if="overdue.length === 0"
      icon="i-lucide-check-check"
      :title="t('dashboard.overdue.empty')"
    />

    <ul
      v-else
      class="divide-y divide-[var(--color-border-subtle)]"
    >
      <li
        v-for="inv in topFive"
        :key="inv.id"
      >
        <ListRow :to="`/invoices/${inv.id}`">
          <template #leading>
            <span class="text-caption tnum text-subtle w-24 truncate">
              {{ inv.invoice_number }}
            </span>
          </template>
          <template #title>
            {{ inv.patient_name }}
          </template>
          <template #subtitle>
            <span class="text-danger-accent">
              {{ t('dashboard.overdue.daysOverdue', { n: inv.days_overdue }) }}
            </span>
          </template>
          <template #meta>
            <span class="text-ui tnum text-default font-semibold">
              {{ formatMoney(inv.balance_due) }}
            </span>
          </template>
        </ListRow>
      </li>
    </ul>
  </SectionCard>
</template>
