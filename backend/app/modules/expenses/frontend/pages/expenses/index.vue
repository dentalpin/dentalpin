<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useExpenses, type Expense, type ExpenseCategory, type ExpenseMonthlyTotal } from '../../composables/useExpenses'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const expensesApi = useExpenses()

if (!can(PERMISSIONS.expenses.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.expenses.write))

const CATEGORIES: ExpenseCategory[] = [
  'rent', 'utilities', 'salaries', 'supplies', 'equipment', 'insurance', 'maintenance', 'other'
]
const categoryOptions = computed(() =>
  CATEGORIES.map(c => ({ value: c, label: t(`expenses.categories.${c}`) }))
)

const items = ref<Expense[]>([])
const total = ref(0)
const loading = ref(false)

const now = new Date()
const filterCategory = ref<ExpenseCategory | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await expensesApi.list({ category: filterCategory.value, page: 1, page_size: 100 })
    items.value = res.data
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const monthlyTotals = ref<ExpenseMonthlyTotal[]>([])
async function loadMonthlyTotals() {
  const res = await expensesApi.monthlyTotals(now.getFullYear(), now.getMonth() + 1)
  monthlyTotals.value = res.data
}

onMounted(async () => {
  await Promise.all([load(), loadMonthlyTotals()])
})

watch(filterCategory, load)

// --- Add expense modal ---
const showModal = ref(false)
const saving = ref(false)
const form = ref({
  category: 'other' as ExpenseCategory,
  amount: 0,
  expense_date: new Date().toISOString().slice(0, 10),
  description: ''
})

async function submit() {
  saving.value = true
  try {
    await expensesApi.create({
      category: form.value.category,
      amount: form.value.amount,
      expense_date: form.value.expense_date,
      description: form.value.description || undefined
    })
    showModal.value = false
    form.value = { category: 'other', amount: 0, expense_date: new Date().toISOString().slice(0, 10), description: '' }
    await Promise.all([load(), loadMonthlyTotals()])
  } finally {
    saving.value = false
  }
}

async function remove(id: string) {
  await expensesApi.remove(id)
  await Promise.all([load(), loadMonthlyTotals()])
}

const columns = [
  { accessorKey: 'expense_date', header: t('expenses.date') },
  { accessorKey: 'category', header: t('expenses.category') },
  { accessorKey: 'amount', header: t('expenses.amount') },
  { accessorKey: 'description', header: t('expenses.description') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('expenses.title') }}
      </h1>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="showModal = true"
      >
        {{ t('expenses.add') }}
      </UButton>
    </div>

    <div class="flex flex-wrap gap-2">
      <UButton
        v-for="mt in monthlyTotals"
        :key="mt.category"
        variant="soft"
        size="sm"
      >
        {{ t(`expenses.categories.${mt.category}`) }}: {{ mt.total }}
      </UButton>
    </div>

    <USelect
      v-model="filterCategory"
      :items="categoryOptions"
      :placeholder="t('expenses.filterByCategory')"
      class="max-w-xs"
    />

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #actions-cell="{ row }">
        <UButton
          v-if="canWrite"
          icon="i-lucide-trash-2"
          variant="ghost"
          color="error"
          size="xs"
          @click="remove(row.original.id)"
        />
      </template>
    </UTable>

    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('expenses.add') }}
          </h2>
          <USelect v-model="form.category" :items="categoryOptions" />
          <UInput v-model.number="form.amount" type="number" step="0.01" :placeholder="t('expenses.amount')" />
          <UInput v-model="form.expense_date" type="date" />
          <UInput v-model="form.description" :placeholder="t('expenses.description')" />
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="showModal = false">
              {{ t('actions.cancel') }}
            </UButton>
            <UButton :loading="saving" @click="submit">
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
