<script setup lang="ts">
/**
 * DataListLayout — the canonical shell for the four list pages.
 *
 * Wraps: PageHeader · toolbar slot (filters) · body slot · footer
 * (pagination + result count). Handles loading / empty / error states.
 *
 * Layout intentionally close to the existing /budgets and /invoices
 * pages so the visual transition is minimal; the win is in the
 * primitives and URL state, not in a redesigned shell.
 */
interface Props {
  title: string
  subtitle?: string
  loading: boolean
  /** True when the result set is empty AND not loading. */
  empty: boolean
  /** Optional error message. */
  error?: string | null
  /** Pagination + count info. */
  page: number
  pageSize: number
  total: number
  totalPages: number
  /** Skeleton row count while loading. */
  skeletonRows?: number
}

withDefaults(defineProps<Props>(), {
  subtitle: undefined,
  error: null,
  skeletonRows: 5
})

const emit = defineEmits<{
  'update:page': [page: number]
}>()

const { t } = useI18n()

function onPage(value: number) {
  emit('update:page', value)
}
</script>

<template>
  <div>
    <PageHeader
      :title="title"
      :subtitle="subtitle"
    >
      <template
        v-if="$slots.actions"
        #actions
      >
        <slot name="actions" />
      </template>
    </PageHeader>

    <!-- Toolbar (search + filters) -->
    <div
      v-if="$slots.toolbar"
      class="mb-[var(--density-gap,1rem)]"
    >
      <slot name="toolbar" />
    </div>

    <UCard>
      <!-- Error -->
      <UAlert
        v-if="error"
        color="error"
        variant="soft"
        :title="t('common.error')"
        :description="error"
        class="mb-3"
      />

      <!-- Loading -->
      <div
        v-if="loading"
        class="space-y-3"
      >
        <USkeleton
          v-for="i in skeletonRows"
          :key="i"
          class="h-14 w-full"
        />
      </div>

      <!-- Empty -->
      <slot
        v-else-if="empty"
        name="empty"
      >
        <EmptyState
          icon="i-lucide-inbox"
          :title="t('lists.empty.title')"
          :description="t('lists.empty.description')"
        />
      </slot>

      <!-- Rows -->
      <div
        v-else
        class="divide-y divide-[var(--color-border-subtle)]"
      >
        <slot name="rows" />
      </div>

      <!-- Footer: count + pagination -->
      <div
        v-if="!loading && !empty"
        class="mt-3 flex flex-col gap-3 border-t border-subtle pt-3 text-caption text-subtle tnum sm:flex-row sm:items-center sm:justify-between"
      >
        <span>
          {{ t('lists.resultCount', { shown: Math.min(page * pageSize, total), total }) }}
        </span>
        <PaginationBar
          :page="page"
          :total-pages="totalPages"
          :total="total"
          :page-size="pageSize"
          @update:page="onPage"
        />
      </div>
    </UCard>
  </div>
</template>
