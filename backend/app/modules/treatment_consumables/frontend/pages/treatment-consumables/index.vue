<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import type { TreatmentConsumable } from "~/composables/useTreatmentConsumables";
import type { InventoryItem } from "~/composables/useInventory";

const { searchItems, getItem, getItemName } = useCatalog();
const { list: listInventory } = useInventory();
const { list, create, update, remove } = useTreatmentConsumables();

// --- "Add a link" form: treatment picker (type-ahead, no page cap) ---
const treatmentQuery = ref("");
const treatmentResults = ref<
  Array<{ id: string; internal_code: string; names: Record<string, string> }>
>([]);
const newTreatmentId = ref<string | null>(null);
const newTreatmentLabel = ref<string>("");
let treatmentDebounce: ReturnType<typeof setTimeout> | null = null;

watch(treatmentQuery, (q) => {
  if (treatmentDebounce) clearTimeout(treatmentDebounce);
  const trimmed = q.trim();
  if (trimmed.length < 1) {
    treatmentResults.value = [];
    return;
  }
  treatmentDebounce = setTimeout(async () => {
    treatmentResults.value = await searchItems(trimmed, 20);
  }, 300);
});

function pickTreatment(item: { id: string; internal_code: string; names: Record<string, string> }) {
  newTreatmentId.value = item.id;
  newTreatmentLabel.value = `${item.internal_code} — ${item.names?.en ?? item.names?.es ?? item.internal_code}`;
  treatmentLabelCache.value[item.id] = newTreatmentLabel.value;
  treatmentQuery.value = "";
  treatmentResults.value = [];
}

// --- "Add a link" form: inventory-item picker (type-ahead, no page cap) ---
const inventoryQuery = ref("");
const inventoryResults = ref<InventoryItem[]>([]);
const newInventoryItemId = ref<string | null>(null);
const newInventoryItemLabel = ref<string>("");
const newQuantity = ref<number>(1);
let inventoryDebounce: ReturnType<typeof setTimeout> | null = null;

watch(inventoryQuery, (q) => {
  if (inventoryDebounce) clearTimeout(inventoryDebounce);
  const trimmed = q.trim();
  if (trimmed.length < 1) {
    inventoryResults.value = [];
    return;
  }
  inventoryDebounce = setTimeout(async () => {
    const res = await listInventory({ search: trimmed, page_size: 20 });
    inventoryResults.value = res.data;
  }, 300);
});

function pickInventoryItem(item: InventoryItem) {
  newInventoryItemId.value = item.id;
  newInventoryItemLabel.value = item.unit ? `${item.name} (${item.unit})` : item.name;
  inventoryLabelCache.value[item.id] = newInventoryItemLabel.value;
  inventoryQuery.value = "";
  inventoryResults.value = [];
}

function resetAddForm() {
  newTreatmentId.value = null;
  newTreatmentLabel.value = "";
  newInventoryItemId.value = null;
  newInventoryItemLabel.value = "";
  newQuantity.value = 1;
}

async function addLink() {
  if (!newTreatmentId.value || !newInventoryItemId.value) return;
  await create({
    treatment_id: newTreatmentId.value,
    inventory_item_id: newInventoryItemId.value,
    quantity_needed: newQuantity.value,
  });
  resetAddForm();
  await loadAllLinks();
}

// --- Full history: every confirmed link across every treatment ---
const allLinks = ref<TreatmentConsumable[]>([]);
const pending = ref(false);

// Display-name caches. Neither catalog nor inventory has a batch-by-ids
// endpoint, so: treatments are resolved one at a time via getItem()
// (cheap -- typically only a handful of distinct treatments appear in
// the history); inventory items are resolved via a one-time paginated
// full-list fetch (a stock list is bounded, unlike "every keystroke").
const treatmentLabelCache = ref<Record<string, string>>({});
const inventoryLabelCache = ref<Record<string, string>>({});
let inventoryMapLoaded = false;

async function ensureInventoryLabelMap() {
  if (inventoryMapLoaded) return;
  let page = 1;
  const pageSize = 1000;
  for (;;) {
    const res = await listInventory({ page, page_size: pageSize });
    for (const item of res.data) {
      inventoryLabelCache.value[item.id] = item.unit ? `${item.name} (${item.unit})` : item.name;
    }
    if (page * pageSize >= res.total) break;
    page += 1;
  }
  inventoryMapLoaded = true;
}

async function ensureTreatmentLabels(treatmentIds: string[]) {
  const missing = [...new Set(treatmentIds)].filter((id) => !(id in treatmentLabelCache.value));
  await Promise.all(
    missing.map(async (id) => {
      const item = await getItem(id);
      if (item) {
        treatmentLabelCache.value[id] = `${item.internal_code} — ${getItemName(item)}`;
      }
    }),
  );
}

async function loadAllLinks() {
  pending.value = true;
  try {
    const rows: TreatmentConsumable[] = [];
    let page = 1;
    const pageSize = 200;
    for (;;) {
      const res = await list({ page, page_size: pageSize });
      rows.push(...res.data);
      if (page * pageSize >= res.total) break;
      page += 1;
    }
    allLinks.value = rows;
    await Promise.all([
      ensureInventoryLabelMap(),
      ensureTreatmentLabels(rows.map((r) => r.treatment_id)),
    ]);
  } finally {
    pending.value = false;
  }
}

function treatmentLabel(id: string): string {
  return treatmentLabelCache.value[id] ?? id;
}
function inventoryLabel(id: string): string {
  return inventoryLabelCache.value[id] ?? id;
}

async function updateQuantity(link: TreatmentConsumable, quantity: number) {
  await update(link.id, { quantity_needed: quantity });
  await loadAllLinks();
}

async function removeLink(link: TreatmentConsumable) {
  await remove(link.id);
  await loadAllLinks();
}

onMounted(loadAllLinks);
</script>

<template>
  <div class="p-4 space-y-6">
    <h1 class="text-xl font-semibold">{{ $t("nav.treatmentConsumables") }}</h1>

    <div class="border rounded p-4 space-y-3">
      <h2 class="font-medium">{{ $t("treatmentConsumables.addLink") }}</h2>
      <div class="flex flex-wrap gap-2 items-end">
        <UFormGroup :label="$t('treatmentConsumables.selectTreatment')">
          <div v-if="newTreatmentId" class="flex items-center gap-2">
            <span>{{ newTreatmentLabel }}</span>
            <UButton size="xs" variant="ghost" @click="newTreatmentId = null; newTreatmentLabel = ''">
              {{ $t("treatmentConsumables.change") }}
            </UButton>
          </div>
          <div v-else class="relative">
            <UInput
              v-model="treatmentQuery"
              :placeholder="$t('treatmentConsumables.searchTreatments')"
            />
            <ul
              v-if="treatmentResults.length"
              class="absolute z-10 mt-1 w-full bg-white dark:bg-gray-900 border rounded shadow max-h-64 overflow-auto"
            >
              <li
                v-for="item in treatmentResults"
                :key="item.id"
                class="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
                @click="pickTreatment(item)"
              >
                {{ item.internal_code }} — {{ item.names?.en ?? item.names?.es ?? item.internal_code }}
              </li>
            </ul>
          </div>
        </UFormGroup>

        <UFormGroup :label="$t('treatmentConsumables.inventoryItem')">
          <div v-if="newInventoryItemId" class="flex items-center gap-2">
            <span>{{ newInventoryItemLabel }}</span>
            <UButton
              size="xs"
              variant="ghost"
              @click="newInventoryItemId = null; newInventoryItemLabel = ''"
            >
              {{ $t("treatmentConsumables.change") }}
            </UButton>
          </div>
          <div v-else class="relative">
            <UInput
              v-model="inventoryQuery"
              :placeholder="$t('treatmentConsumables.searchInventory')"
            />
            <ul
              v-if="inventoryResults.length"
              class="absolute z-10 mt-1 w-full bg-white dark:bg-gray-900 border rounded shadow max-h-64 overflow-auto"
            >
              <li
                v-for="item in inventoryResults"
                :key="item.id"
                class="px-3 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
                @click="pickInventoryItem(item)"
              >
                {{ item.name }}<span v-if="item.unit"> ({{ item.unit }})</span>
              </li>
            </ul>
          </div>
        </UFormGroup>

        <UFormGroup :label="$t('treatmentConsumables.quantity')">
          <UInput v-model.number="newQuantity" type="number" min="0.01" step="0.01" />
        </UFormGroup>

        <UButton :disabled="!newTreatmentId || !newInventoryItemId" @click="addLink">
          {{ $t("treatmentConsumables.add") }}
        </UButton>
      </div>
    </div>

    <div class="space-y-2">
      <h2 class="font-medium">{{ $t("treatmentConsumables.allLinks") }}</h2>
      <div v-if="pending">{{ $t("treatmentConsumables.loading") }}</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left">
            <th>{{ $t("treatmentConsumables.selectTreatment") }}</th>
            <th>{{ $t("treatmentConsumables.inventoryItem") }}</th>
            <th>{{ $t("treatmentConsumables.quantity") }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="link in allLinks" :key="link.id">
            <td>{{ treatmentLabel(link.treatment_id) }}</td>
            <td>{{ inventoryLabel(link.inventory_item_id) }}</td>
            <td>
              <UInput
                type="number"
                min="0.01"
                step="0.01"
                :model-value="link.quantity_needed"
                @change="(e: Event) => updateQuantity(link, Number((e.target as HTMLInputElement).value))"
              />
            </td>
            <td>
              <UButton color="red" variant="ghost" @click="removeLink(link)">
                {{ $t("treatmentConsumables.remove") }}
              </UButton>
            </td>
          </tr>
          <tr v-if="!allLinks.length">
            <td colspan="4" class="text-gray-500 py-4">
              {{ $t("treatmentConsumables.empty") }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
