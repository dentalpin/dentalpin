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

const total = computed(() => overdue.value.length)
const balance = computed(() =>
  overdue.value.reduce((sum, i) => sum + Number(i.balance_due ?? 0), 0)
)

const surfaceClass = computed(() =>
  total.value === 0 ? 'bg-surface ring-1 ring-[var(--color-border)] shadow-[var(--shadow-sm)]' : 'alert-surface-danger'
)

const { format: formatMoney } = useCurrency()
</script>

<template>
  <NuxtLink
    to="/invoices?filter=overdue"
    class="block rounded-token-lg px-4 py-3 transition-[box-shadow] hover:ring-1 hover:ring-[var(--color-border-strong)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-primary)]"
    :class="surfaceClass"
  >
    <div class="flex items-center justify-between mb-1">
      <p
        class="text-caption"
        :class="total === 0 ? 'text-subtle' : 'opacity-75'"
      >
        {{ t('dashboard.overdue.title') }}
      </p>
      <UIcon
        name="i-lucide-alert-triangle"
        class="w-4 h-4"
        :class="total === 0 ? 'text-subtle' : 'opacity-75'"
      />
    </div>

    <USkeleton
      v-if="pending"
      class="h-8 w-16 mb-2"
    />
    <p
      v-else
      class="text-display tnum"
      :class="total === 0 ? 'text-default' : ''"
    >
      {{ total }}
    </p>

    <p
      v-if="!pending && total > 0"
      class="text-caption tnum opacity-75 mt-1"
    >
      {{ formatMoney(balance) }}
    </p>
    <p
      v-else-if="!pending"
      class="text-caption text-subtle mt-1"
    >
      {{ t('dashboard.overdue.empty') }}
    </p>
  </NuxtLink>
</template>
