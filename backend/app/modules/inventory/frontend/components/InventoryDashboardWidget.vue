<script setup lang="ts">
const { t } = useI18n()
const inventoryApi = useInventory()

const lowStockCount = ref<number | null>(null)
const isLoading = ref(false)

async function load() {
  isLoading.value = true
  try {
    const res = await inventoryApi.list({ low_stock_only: true, page: 1, page_size: 1 })
    lowStockCount.value = res.total
  } catch {
    lowStockCount.value = null
  } finally {
    isLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <UCard v-if="isLoading || (lowStockCount ?? 0) > 0" :ui="{ body: 'p-3' }">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-triangle-alert" class="w-4 h-4 text-warning" />
          <span class="font-medium">{{ t('inventory.dashboard.title') }}</span>
        </div>
        <NuxtLink to="/inventory" class="text-primary-accent hover:underline text-caption">
          {{ t('inventory.dashboard.viewAll') }} →
        </NuxtLink>
      </div>
    </template>

    <USkeleton v-if="isLoading" class="h-12 w-full" />
    <div v-else class="text-center">
      <div class="text-h2 text-warning tnum">
        {{ lowStockCount }}
      </div>
      <div class="text-caption text-subtle">
        {{ t('inventory.dashboard.lowStock') }}
      </div>
    </div>
  </UCard>
</template>
