<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import type { StaffActivityLog } from "~/composables/useStaffActivity";

const { list } = useStaffActivity();

const items = ref<StaffActivityLog[]>([]);
const total = ref(0);
const pending = ref(false);
const page = ref(1);
const pageSize = 25;

const filters = reactive<Record<string, string>>({
  user_id: "",
  action_type: "",
  date_from: "",
  date_to: "",
  search: "",
});

const columns = [
  { accessorKey: "timestamp", header: "Date" },
  { accessorKey: "user_id", header: "Staff" },
  { accessorKey: "action_type", header: "Action" },
  { accessorKey: "entity_type", header: "Entity" },
  { accessorKey: "entity_id", header: "Entity ID" },
];

async function fetchLogs() {
  pending.value = true;
  try {
    const res = await list({
      ...filters,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    });
    items.value = res.items;
    total.value = res.total;
  } finally {
    pending.value = false;
  }
}

watch(page, fetchLogs);

function applyFilters() {
  page.value = 1;
  fetchLogs();
}

onMounted(fetchLogs);
</script>

<template>
  <div class="p-4 space-y-4">
    <h1 class="text-xl font-semibold">{{ $t("nav.staffActivity") }}</h1>

    <div class="flex flex-wrap gap-2 items-end">
      <UFormGroup :label="$t('staffActivity.filters.staff')">
        <UInput v-model="filters.user_id" placeholder="User ID" />
      </UFormGroup>
      <UFormGroup :label="$t('staffActivity.filters.actionType')">
        <UInput v-model="filters.action_type" placeholder="e.g. appointment.completed" />
      </UFormGroup>
      <UFormGroup :label="$t('staffActivity.filters.dateFrom')">
        <UInput v-model="filters.date_from" type="date" />
      </UFormGroup>
      <UFormGroup :label="$t('staffActivity.filters.dateTo')">
        <UInput v-model="filters.date_to" type="date" />
      </UFormGroup>
      <UFormGroup :label="$t('staffActivity.filters.search')">
        <UInput v-model="filters.search" placeholder="Search..." />
      </UFormGroup>
      <UButton @click="applyFilters">{{ $t("staffActivity.filters.apply") }}</UButton>
    </div>

    <UTable :data="items" :columns="columns" :loading="pending">
      <template #timestamp-cell="{ row }">
        {{ new Date(row.getValue('timestamp')).toLocaleString() }}
      </template>
      <template #entity_id-cell="{ row }">
        <span v-if="row.original.entity_type">
          {{ row.original.entity_type }}#{{ row.original.entity_id }}
        </span>
      </template>
    </UTable>

    <UPagination v-model="page" :page-count="pageSize" :total="total" />
  </div>
</template>