<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import {
  useMedicationCatalog,
  type MedicationCatalogItem,
  type MedicationForm
} from '../../composables/useMedicationCatalog'

const { t } = useI18n()
const { can } = usePermissions()
const medsApi = useMedicationCatalog()

// No read guard here: the settings registry already hides the entry
// (and [page].vue renders the locked state) for users without
// `medication_catalog.read`. A top-level await would also make this an
// async setup component, which the registry mounts outside Suspense.
const canWrite = computed(() => can(PERMISSIONS.medicationCatalog.write))

const FORMS: MedicationForm[] = [
  'tablet', 'capsule', 'syrup', 'suspension', 'injection', 'topical',
  'drops', 'spray', 'mouthwash', 'gel', 'cream', 'paste', 'varnish', 'other'
]
// Nuxt UI v3's USelect cannot clear a selected '' value (Reka Select
// gotcha, #277) — model an explicit "all" sentinel and map it to
// undefined for the API call.
const filterForm = ref<MedicationForm | 'all'>('all')
const filterFormOptions = computed(() => [
  { value: 'all', label: t('medications.allForms') },
  ...FORMS.map(f => ({ value: f, label: t(`medications.forms.${f}`) }))
])
const formOptions = computed(() =>
  FORMS.map(f => ({ value: f, label: t(`medications.forms.${f}`) }))
)

// --- List state (server-side pagination) ----------------------------------
const items = ref<MedicationCatalogItem[]>([])
const total = ref(0)
const loading = ref(false)
const page = ref(1)
const PAGE_SIZE = 20
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const search = ref('')
const filterActiveOnly = ref<boolean>(false)

let debounce: ReturnType<typeof setTimeout> | undefined
watch(search, () => {
  clearTimeout(debounce)
  debounce = setTimeout(() => {
    page.value = 1
    load()
  }, 300)
})

async function load() {
  loading.value = true
  try {
    const res = await medsApi.list({
      q: search.value || undefined,
      form: filterForm.value === 'all' ? undefined : filterForm.value,
      is_active: filterActiveOnly.value ? true : undefined,
      page: page.value,
      page_size: PAGE_SIZE
    })
    items.value = res.data
    total.value = res.total
    // A filter change can drop us past the last page.
    if (page.value > totalPages.value) {
      page.value = totalPages.value
      await load()
    }
  } finally {
    loading.value = false
  }
}

function onPage(p: number) {
  page.value = p
  load()
}

watch([filterForm, filterActiveOnly], () => {
  page.value = 1
  load()
})

onMounted(load)

// --- Add / edit modal -------------------------------------------------------
const showModal = ref(false)
const editingId = ref<string | null>(null)
const saving = ref(false)
const form = ref({
  name: '',
  dose: '',
  unit: '',
  form: 'tablet' as MedicationForm,
  requires_prescription: true,
  is_active: true
})

function openAdd() {
  editingId.value = null
  form.value = { name: '', dose: '', unit: '', form: 'tablet', requires_prescription: true, is_active: true }
  showModal.value = true
}

function openEdit(item: MedicationCatalogItem) {
  editingId.value = item.id
  form.value = {
    name: item.name,
    dose: item.dose ?? '',
    unit: item.unit ?? '',
    form: item.form,
    requires_prescription: item.requires_prescription,
    is_active: item.is_active
  }
  showModal.value = true
}

// useApi intentionally rethrows 409s — surface the duplicate-name
// message in the modal instead of leaving it silently open (#279 review).
const formError = ref('')

async function submit() {
  formError.value = ''
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      dose: form.value.dose || null,
      unit: form.value.unit || null,
      form: form.value.form,
      requires_prescription: form.value.requires_prescription,
      is_active: form.value.is_active
    }
    if (editingId.value) {
      await medsApi.update(editingId.value, payload)
    } else {
      await medsApi.create(payload)
    }
    showModal.value = false
    await load()
  } catch (err: unknown) {
    // ofetch's FetchError carries the ApiResponse envelope in `.data`.
    const fetchErr = err as { data?: { message?: string } | undefined }
    formError.value = fetchErr?.data?.message || t('medications.duplicateName')
  } finally {
    saving.value = false
  }
}

// --- Delete confirmation (same pattern as the other modules) ----------------
const showDeleteConfirm = ref(false)
const itemToDelete = ref<MedicationCatalogItem | null>(null)
const isDeleting = ref(false)

function confirmDelete(item: MedicationCatalogItem) {
  itemToDelete.value = item
  showDeleteConfirm.value = true
}

async function handleDelete() {
  if (!itemToDelete.value) return
  isDeleting.value = true
  try {
    await medsApi.remove(itemToDelete.value.id)
    showDeleteConfirm.value = false
    await load()
  } finally {
    isDeleting.value = false
  }
}

// --- Seed --------------------------------------------------------------------
const seeding = ref(false)
const seedToast = ref('')
async function runSeed() {
  seeding.value = true
  try {
    const res = await medsApi.seed()
    seedToast.value = t('medications.seedDone', {
      created: res.data.created,
      skipped: res.data.skipped
    })
    setTimeout(() => (seedToast.value = ''), 5000)
    await load()
  } finally {
    seeding.value = false
  }
}

const columns = computed(() => [
  { accessorKey: 'name', header: t('medications.name') },
  { accessorKey: 'dose', header: t('medications.dose') },
  { accessorKey: 'unit', header: t('medications.unit') },
  { accessorKey: 'form', header: t('medications.form') },
  { accessorKey: 'requires_prescription', header: t('medications.prescription') },
  { accessorKey: 'is_active', header: t('medications.status') },
  { id: 'actions' }
])
</script>

<template>
  <div class="space-y-4 p-4">
    <div class="flex flex-wrap items-start justify-between gap-2">
      <div>
        <h1 class="text-h3 text-default">
          {{ t('medications.title') }}
        </h1>
        <p class="text-ui text-subtle">
          {{ t('medications.subtitle') }}
        </p>
      </div>
      <div class="flex gap-2">
        <UButton
          v-if="canWrite"
          variant="outline"
          icon="i-lucide-database"
          :loading="seeding"
          @click="runSeed"
        >
          {{ t('medications.seed') }}
        </UButton>
        <UButton
          v-if="canWrite"
          icon="i-lucide-plus"
          @click="openAdd"
        >
          {{ t('medications.add') }}
        </UButton>
      </div>
    </div>

    <p
      v-if="seedToast"
      class="text-sm text-primary"
      role="status"
    >
      {{ seedToast }}
    </p>

    <div class="flex flex-wrap items-center gap-2">
      <UInput
        v-model="search"
        :placeholder="t('medications.search')"
        icon="i-lucide-search"
        class="max-w-xs"
      />
      <USelect
        v-model="filterForm"
        :items="filterFormOptions"
        class="max-w-48"
      />
      <USwitch v-model="filterActiveOnly" />
      <span class="text-ui text-subtle">{{ t('medications.statusActive') }}</span>
    </div>

    <UTable
      :data="items"
      :columns="columns"
      :loading="loading"
    >
      <template #form-cell="{ row }">
        <UBadge
          variant="subtle"
          size="sm"
        >
          {{ t(`medications.forms.${row.original.form}`) }}
        </UBadge>
      </template>
      <template #requires_prescription-cell="{ row }">
        <UIcon
          :name="row.original.requires_prescription ? 'i-lucide-pill' : 'i-lucide-minus'"
          :class="row.original.requires_prescription ? 'text-primary' : 'text-subtle'"
        />
      </template>
      <template #is_active-cell="{ row }">
        <UBadge
          :color="row.original.is_active ? 'success' : 'neutral'"
          variant="subtle"
          size="sm"
        >
          {{ t(row.original.is_active ? 'medications.active' : 'medications.inactive') }}
        </UBadge>
      </template>
      <template #actions-cell="{ row }">
        <div class="flex gap-1">
          <UButton
            v-if="canWrite"
            icon="i-lucide-pencil"
            variant="ghost"
            size="xs"
            :aria-label="t('medications.edit')"
            @click="openEdit(row.original)"
          />
          <UButton
            v-if="canWrite"
            icon="i-lucide-trash-2"
            variant="ghost"
            color="error"
            size="xs"
            :aria-label="t('medications.delete')"
            @click="confirmDelete(row.original)"
          />
        </div>
      </template>
    </UTable>

    <PaginationBar
      :page="page"
      :total-pages="totalPages"
      :total="total"
      :page-size="PAGE_SIZE"
      @update:page="onPage"
    />

    <!-- Add / edit modal -->
    <UModal v-model:open="showModal">
      <template #content>
        <div class="p-4 space-y-4">
          <h2 class="text-h3 text-default">
            {{ editingId ? t('medications.edit') : t('medications.add') }}
          </h2>
          <UInput
            v-model="form.name"
            :placeholder="t('medications.name')"
          />
          <div class="flex gap-2">
            <UInput
              v-model="form.dose"
              :placeholder="t('medications.dose')"
              class="w-32"
            />
            <UInput
              v-model="form.unit"
              :placeholder="t('medications.unit')"
              class="w-32"
            />
          </div>
          <USelect
            v-model="form.form"
            :items="[...formOptions]"
            :placeholder="t('medications.forms.tablet')"
          />
          <div class="flex items-center gap-2">
            <USwitch v-model="form.requires_prescription" />
            <span class="text-ui">{{ t('medications.prescription') }}</span>
          </div>
          <div class="flex items-center gap-2">
            <USwitch v-model="form.is_active" />
            <span class="text-ui">{{ t('medications.status') }}</span>
          </div>
          <p
            v-if="formError"
            class="text-sm text-error"
            role="alert"
          >
            {{ formError }}
          </p>
          <div class="flex justify-end gap-2">
            <UButton
              variant="ghost"
              @click="showModal = false"
            >
              {{ t('actions.cancel') }}
            </UButton>
            <UButton
              :loading="saving"
              :disabled="!form.name.trim()"
              @click="submit"
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
            {{ t('medications.deleteTitle') }}
          </h2>
          <p class="text-ui text-subtle">
            {{ t('medications.deleteMessage') }}
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
              {{ t('medications.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
