<script setup lang="ts">
const { t } = useI18n()
const labOrdersApi = useLabOrders()

const sentCount = ref<number | null>(null)
const inProgressCount = ref<number | null>(null)
const readyCount = ref<number | null>(null)
const isLoading = ref(false)

async function load() {
  isLoading.value = true
  try {
    const [sent, inProgress, ready] = await Promise.all([
      labOrdersApi.list({ order_status: 'sent', page: 1, page_size: 1 }),
      labOrdersApi.list({ order_status: 'in_progress', page: 1, page_size: 1 }),
      labOrdersApi.list({ order_status: 'ready', page: 1, page_size: 1 })
    ])
    sentCount.value = sent.total
    inProgressCount.value = inProgress.total
    readyCount.value = ready.total
  } catch {
    sentCount.value = null
    inProgressCount.value = null
    readyCount.value = null
  } finally {
    isLoading.value = false
  }
}

onMounted(load)

const hasPending = computed(() =>
  (sentCount.value ?? 0) + (inProgressCount.value ?? 0) + (readyCount.value ?? 0) > 0
)
</script>

<template>
  <UCard v-if="isLoading || hasPending" :ui="{ body: 'p-3' }">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-flask-conical" class="w-4 h-4 text-default" />
          <span class="font-medium">{{ t('labOrders.dashboard.title') }}</span>
        </div>
        <NuxtLink to="/lab-orders" class="text-primary-accent hover:underline text-caption">
          {{ t('labOrders.dashboard.viewAll') }} →
        </NuxtLink>
      </div>
    </template>

    <USkeleton v-if="isLoading" class="h-12 w-full" />
    <div v-else class="grid grid-cols-3 gap-2 text-center">
      <div>
        <div class="text-h2 text-default tnum">
          {{ sentCount }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('labOrders.statuses.sent') }}
        </div>
      </div>
      <div>
        <div class="text-h2 text-default tnum">
          {{ inProgressCount }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('labOrders.statuses.in_progress') }}
        </div>
      </div>
      <div>
        <div class="text-h2 text-warning tnum">
          {{ readyCount }}
        </div>
        <div class="text-caption text-subtle">
          {{ t('labOrders.statuses.ready') }}
        </div>
      </div>
    </div>
  </UCard>
</template>
