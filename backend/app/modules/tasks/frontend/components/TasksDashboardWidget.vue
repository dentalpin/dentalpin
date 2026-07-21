<script setup lang="ts">
const { t } = useI18n()
const tasksApi = useTasks()

const openCount = ref<number | null>(null)
const isLoading = ref(false)

async function load() {
  isLoading.value = true
  try {
    const res = await tasksApi.list({ task_status: 'open', page: 1, page_size: 1 })
    openCount.value = res.total
  } catch {
    openCount.value = null
  } finally {
    isLoading.value = false
  }
}

onMounted(load)
</script>

<template>
  <UCard :ui="{ body: 'p-3' }">
    <template #header>
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <UIcon name="i-lucide-list-checks" class="w-4 h-4 text-default" />
          <span class="font-medium">{{ t('tasks.dashboard.title') }}</span>
        </div>
        <NuxtLink to="/tasks" class="text-primary-accent hover:underline text-caption">
          {{ t('tasks.dashboard.viewAll') }} →
        </NuxtLink>
      </div>
    </template>

    <USkeleton v-if="isLoading || openCount === null" class="h-12 w-full" />
    <div v-else class="text-center">
      <div class="text-h2 text-default tnum">
        {{ openCount }}
      </div>
      <div class="text-caption text-subtle">
        {{ t('tasks.dashboard.open') }}
      </div>
    </div>
  </UCard>
</template>
