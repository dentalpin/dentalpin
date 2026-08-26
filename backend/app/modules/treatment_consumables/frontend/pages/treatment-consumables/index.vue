<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorDetail, errorStatus } from '~~/app/utils/error'
import {
  useTreatmentConsumables,
  type ConsumableLink,
  type LinkOptionTreatment,
  type LinkOptionItem
} from '../../composables/useTreatmentConsumables'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const linksApi = useTreatmentConsumables()

if (!can(PERMISSIONS.treatmentConsumables.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.treatmentConsumables.write))

// "2.00" -> "2", "1.50" -> "1.5" — Numeric(10,2) noise trimmed for display.
const fmtQty = (v: string) => String(Number(v))

function notifyError(e: unknown) {
  toast.add({
    title: t('common.error'),
    description: errorStatus(e) === 409 ? t('consumables.duplicate') : errorDetail(e),
    color: 'error'
  })
}

// --- History table (server-side pagination) --------------------------------
const items = ref<ConsumableLink[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

async function load() {
  loading.value = true
  try {
    const res = await linksApi.list({ page: page.value, page_size: PAGE_SIZE })
    items.value = res.data
    total.value = res.total
    if (page.value > totalPages.value) {
      page.value = totalPages.value
      await load()
    }
  } catch (e) {
    notifyError(e)
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  load()
}

onMounted(load)

// --- Create modal: search-based pickers into both modules -------------------
const showModal = ref(false)
const saving = ref(false)

const treatmentQuery = ref('')
const itemQuery = ref('')
const treatmentOptions = ref<LinkOptionTreatment[]>([])
const itemOptions = ref<LinkOptionItem[]>([])
const selectedTreatment = ref<LinkOptionTreatment | null>(null)
const selectedItem = ref<LinkOptionItem | null>(null)
const quantity = ref('1')
const note = ref('')

// A narrowed query can hide the current pick — keep it listed so the
// selection stays visible (and revocable) while searching the other side.
function pinSelected<T extends { id: string }>(options: T[], selected: T | null): T[] {
  if (!selected || options.some(o => o.id === selected.id)) return options
  return [selected, ...options]
}
const treatmentList = computed(() => pinSelected(treatmentOptions.value, selectedTreatment.value))
const itemList = computed(() => pinSelected(itemOptions.value, selectedItem.value))

async function searchTreatments() {
  try {
    const res = await linksApi.linkOptions(treatmentQuery.value || undefined)
    treatmentOptions.value = res.data.treatments
  } catch (e) {
    notifyError(e)
  }
}

async function searchItems() {
  try {
    const res = await linksApi.linkOptions(itemQuery.value || undefined)
    itemOptions.value = res.data.items
  } catch (e) {
    notifyError(e)
  }
}

let treatmentDebounce: ReturnType<typeof setTimeout> | undefined
let itemDebounce: ReturnType<typeof setTimeout> | undefined
watch(treatmentQuery, () => {
  clearTimeout(treatmentDebounce)
  treatmentDebounce = setTimeout(searchTreatments, 300)
})
watch(itemQuery, () => {
  clearTimeout(itemDebounce)
  itemDebounce = setTimeout(searchItems, 300)
})

async function openAdd() {
  selectedTreatment.value = null
  selectedItem.value = null
  treatmentQuery.value = ''
  itemQuery.value = ''
  quantity.value = '1'
  note.value = ''
  showModal.value = true
  // Both halves come from one request while neither side is filtered.
  try {
    const res = await linksApi.linkOptions()
    treatmentOptions.value = res.data.treatments
    itemOptions.value = res.data.items
  } catch (e) {
    notifyError(e)
  }
}

async function submit() {
  if (!selectedTreatment.value || !selectedItem.value) return
  saving.value = true
  try {
    await linksApi.create({
      catalog_item_id: selectedTreatment.value.id,
      inventory_item_id: selectedItem.value.id,
      quantity: quantity.value || '1',
      note: note.value || null
    })
    toast.add({ title: t('common.success'), color: 'success' })
    showModal.value = false
    await load()
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

// --- Edit modal: quantity + note -------------------------------------------
const showEdit = ref(false)
const editing = ref<ConsumableLink | null>(null)
const editQuantity = ref('1')
const editNote = ref('')

function openEdit(link: ConsumableLink) {
  editing.value = link
  editQuantity.value = fmtQty(link.quantity)
  editNote.value = link.note || ''
  showEdit.value = true
}

async function saveEdit() {
  if (!editing.value) return
  saving.value = true
  try {
    await linksApi.update(editing.value.id, {
      quantity: editQuantity.value || '1',
      note: editNote.value
    })
    toast.add({ title: t('common.success'), color: 'success' })
    showEdit.value = false
    await load()
  } catch (e) {
    notifyError(e)
  } finally {
    saving.value = false
  }
}

// --- Delete confirmation ------------------------------------------------------
const showDeleteConfirm = ref(false)
const linkToDelete = ref<ConsumableLink | null>(null)
const isDeleting = ref(false)

function confirmDelete(link: ConsumableLink) {
  linkToDelete.value = link
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!linkToDelete.value) return
  isDeleting.value = true
  try {
    await linksApi.remove(linkToDelete.value.id)
    toast.add({ title: t('common.success'), color: 'success' })
    showDeleteConfirm.value = false
    await load()
  } catch (e) {
    notifyError(e)
  } finally {
    isDeleting.value = false
  }
}

const columns = computed(() => [
  { accessorKey: 'treatment_name', header: t('consumables.treatment') },
  { accessorKey: 'item_name', header: t('consumables.item') },
  { accessorKey: 'quantity', header: t('consumables.quantity') },
  { accessorKey: 'note', header: t('consumables.note') },
  { id: 'actions' }
])
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h1 class="text-h3 text-default">
          {{ t('consumables.title') }}
        </h1>
        <p class="text-ui text-subtle">
          {{ t('consumables.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        @click="openAdd"
      >
        {{ t('consumables.add') }}
      </UButton>
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #treatment_name-cell="{ row }">
        <span>{{ row.original.treatment_name }}</span>
        <span
          v-if="row.original.treatment_code"
          class="text-xs text-subtle ml-1"
        >({{ row.original.treatment_code }})</span>
      </template>
      <template #quantity-cell="{ row }">
        <UBadge
          variant="subtle"
          size="sm"
          class="tnum"
        >
          {{ fmtQty(row.original.quantity) }}
        </UBadge>
        <span
          v-if="row.original.item_unit"
          class="text-xs text-subtle ml-1"
        >{{ row.original.item_unit }}</span>
      </template>
      <template #note-cell="{ row }">
        <span class="text-ui text-subtle">{{ row.original.note || '—' }}</span>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex justify-end gap-1">
          <UButton
            v-if="canWrite"
            icon="i-lucide-pencil"
            variant="ghost"
            size="xs"
            :aria-label="t('actions.edit')"
            @click="openEdit(row.original)"
          />
          <UButton
            v-if="canWrite"
            icon="i-lucide-unlink"
            variant="ghost"
            color="error"
            size="xs"
            :aria-label="t('consumables.delete')"
            @click="confirmDelete(row.original)"
          />
        </div>
      </template>
      <template #empty>
        <EmptyState
          icon="i-lucide-link-2"
          :title="t('consumables.empty')"
        />
      </template>
    </UTable>

    <PaginationBar
      :page="page"
      :total-pages="totalPages"
      :total="total"
      :page-size="PAGE_SIZE"
      @update:page="onPage"
    />

    <!-- Create modal: search-based pickers into both modules -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4 max-w-xl">
          <h2 class="text-h3 text-default">
            {{ t('consumables.add') }}
          </h2>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div class="space-y-1">
              <p class="text-xs text-subtle">
                {{ t('consumables.treatment') }}
              </p>
              <UInput
                v-model="treatmentQuery"
                icon="i-lucide-search"
                :placeholder="t('consumables.searchTreatments')"
              />
              <div class="max-h-40 overflow-auto rounded border border-default p-1 space-y-1">
                <button
                  v-for="tr in treatmentList"
                  :key="tr.id"
                  type="button"
                  class="w-full text-left px-2 py-1 rounded text-sm hover:bg-elevated"
                  :class="selectedTreatment?.id === tr.id ? 'bg-primary/10 font-medium' : ''"
                  @click="selectedTreatment = tr"
                >
                  {{ tr.name }}
                </button>
                <p
                  v-if="!treatmentList.length"
                  class="text-sm text-subtle px-2 py-1"
                >
                  {{ t('consumables.noMatches') }}
                </p>
              </div>
            </div>
            <div class="space-y-1">
              <p class="text-xs text-subtle">
                {{ t('consumables.item') }}
              </p>
              <UInput
                v-model="itemQuery"
                icon="i-lucide-search"
                :placeholder="t('consumables.searchItems')"
              />
              <div class="max-h-40 overflow-auto rounded border border-default p-1 space-y-1">
                <button
                  v-for="it in itemList"
                  :key="it.id"
                  type="button"
                  class="w-full text-left px-2 py-1 rounded text-sm hover:bg-elevated"
                  :class="selectedItem?.id === it.id ? 'bg-primary/10 font-medium' : ''"
                  @click="selectedItem = it"
                >
                  {{ it.name }}
                </button>
                <p
                  v-if="!itemList.length"
                  class="text-sm text-subtle px-2 py-1"
                >
                  {{ t('consumables.noMatches') }}
                </p>
              </div>
            </div>
          </div>
          <div class="flex flex-wrap gap-2">
            <UFormField
              :label="t('consumables.quantity')"
              class="w-32"
            >
              <UInput
                v-model="quantity"
                type="number"
                step="0.5"
                min="0.5"
              >
                <template
                  v-if="selectedItem?.unit"
                  #trailing
                >
                  <span class="text-xs text-subtle">{{ selectedItem.unit }}</span>
                </template>
              </UInput>
            </UFormField>
            <UFormField
              :label="t('consumables.note')"
              class="flex-1 min-w-48"
            >
              <UInput
                v-model="note"
                :maxlength="200"
                class="w-full"
              />
            </UFormField>
          </div>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showModal = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              :loading="saving"
              :disabled="!selectedTreatment || !selectedItem"
              @click="submit"
            >
              {{ t('consumables.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Edit modal: quantity + note of an existing link -->
    <UModal v-model:open="showEdit">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('consumables.editTitle') }}
          </h2>
          <p
            v-if="editing"
            class="text-ui text-subtle"
          >
            {{ editing.treatment_name }} → {{ editing.item_name }}
          </p>
          <div class="flex flex-wrap gap-2">
            <UFormField
              :label="t('consumables.quantity')"
              class="w-32"
            >
              <UInput
                v-model="editQuantity"
                type="number"
                step="0.5"
                min="0.5"
              >
                <template
                  v-if="editing?.item_unit"
                  #trailing
                >
                  <span class="text-xs text-subtle">{{ editing.item_unit }}</span>
                </template>
              </UInput>
            </UFormField>
            <UFormField
              :label="t('consumables.note')"
              class="flex-1 min-w-48"
            >
              <UInput
                v-model="editNote"
                :maxlength="200"
                class="w-full"
              />
            </UFormField>
          </div>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showEdit = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              :loading="saving"
              @click="saveEdit"
            >
              {{ t('actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Delete confirmation -->
    <UModal v-model:open="showDeleteConfirm">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ t('consumables.deleteTitle') }}
          </h2>
          <p class="text-ui text-subtle">
            {{ t('consumables.deleteMessage') }}
          </p>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showDeleteConfirm = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              color="error"
              :loading="isDeleting"
              @click="handleDelete"
            >
              {{ t('consumables.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
