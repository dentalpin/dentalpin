<script setup lang="ts">
import { ref, watch } from "vue";
import type { TreatmentConsumable } from "~/composables/useTreatmentConsumables";
import type { InventoryItem } from "~/composables/useInventory";

const { searchItems, getItemName } = useCatalog();
const { list: listInventory } = useInventory();
const { list, create, update, remove } = useTreatmentConsumables();

// --- Treatment picker (type-ahead via /items/search, no page cap) ---
const treatmentQuery = ref("");
const treatmentResults = ref<
  Array<{ id: string; internal_code: string; names: Record<string, string> }>
>([]);
const selectedTreatmentId = ref<string | null>(null);
const selectedTreatmentLabel = ref<string>("");
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
  selectedTreatmentId.value = item.id;
  selectedTreatmentLabel.value = `${item.internal_code} — ${item.names?.en ?? item.names?.es ?? item.internal_code}`;
  treatmentQuery.value = "";
  treatmentResults.value = [];
  loadLinks();
}

function clearTreatment() {
  selectedTreatmentId.value = null;
  selectedTreatmentLabel.value = "";
  links.value = [];
}

// --- Inventory-item picker (type-ahead via list({ search }), no page cap) ---
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
  inventoryQuery.value = "";
  inventoryResults.value = [];
}

// --- Linked consumables for the selected treatment ---
const links = ref<TreatmentConsumable[]>([]);
const pending = ref(false);
// Cache of inventory item id -> display label, populated as we encounter them
// (from search picks and from the links list itself).
const inventoryLabelCache = ref<Record<string, string>>({});

async function loadLinks() {
  if (!selectedTreatmentId.value) {
    links.value = [];
    return;
  }
  pending.value = true;
  try {
    const res = await list({ treatment_id: selectedTreatmentId.value, page_size: 200 });
    links.value = res.data;
    await ensureInventoryLabelMap();
  } finally {
    pending.value = false;
  }
}

// Inventory has no get-by-id endpoint, so linked items' display names
// are resolved from a one-time full-list fetch (paginated) into an
// id -> label map, built lazily on first need. This is bounded by
// total inventory size (a stock list), not by search-as-you-type
// traffic, so it's fine even for a few hundred items.
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

function inventoryLabel(id: string): string {
  return inventoryLabelCache.value[id] ?? id;
}

async function addLink() {
  if (!selectedTreatmentId.value || !newInventoryItemId.value) return;
  inventoryLabelCache.value[newInventoryItemId.value] = newInventoryItemLabel.value;
  await create({
    treatment_id: selectedTreatmentId.value,
    inventory_item_id: newInventoryItemId.value,
    quantity_needed: newQuantity.value,
  });
  newInventoryItemId.value = null;
  newInventoryItemLabel.value = "";
  newQuantity.value = 1;
  await loadLinks();
}

async function updateQuantity(link: TreatmentConsumable, quantity: number) {
  await update(link.id, { quantity_needed: quantity });
  await loadLinks();
}

async function removeLink(link: TreatmentConsumable) {
  await remove(link.id);
  await loadLinks();
}
</script>

<template>
  <div class="p-4 space-y-4">
    <h1 class="text-xl font-semibold">{{ $t("nav.treatmentConsumables") }}</h1>

    <UFormGroup :label="$t('treatmentConsumables.selectTreatment')">
      <div v-if="selectedTreatmentId" class="flex items-center gap-2">
        <span class="font-medium">{{ selectedTreatmentLabel }}</span>
        <UButton size="xs" variant="ghost" @click="clearTreatment">
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

    <div v-if="selectedTreatmentId" class="space-y-3">
      <div class="flex flex-wrap gap-2 items-end">
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
        <UButton :disabled="!newInventoryItemId" @click="addLink">
          {{ $t("treatmentConsumables.add") }}
        </UButton>
      </div>

      <div v-if="pending">{{ $t("treatmentConsumables.loading") }}</div>
      <table v-else class="w-full text-sm">
        <thead>
          <tr class="text-left">
            <th>{{ $t("treatmentConsumables.inventoryItem") }}</th>
            <th>{{ $t("treatmentConsumables.quantity") }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr v-for="link in links" :key="link.id">
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
        </tbody>
      </table>
    </div>
  </div>
</template>
