<!--
  UPDATED to Nuxt UI v3 syntax (best-guess fix for: modal opening as an
  empty box, dropdowns not opening). Changes from the v2-style first
  draft:
    - UModal now uses v-model:open (v3 renamed the controlling prop to
      "open"; a bare v-model bound to a nonexistent "modelValue" prop,
      so the dialog shell mounted but never received its open state or
      rendered its slot content -> empty rectangle).
    - USelect now uses :items (array of {label, value}) instead of
      :options + option-attribute/value-attribute, which don't exist
      in v3 -> component had no items to show, so the dropdown had
      nothing to open.
    - UToggle -> USwitch (renamed in v3).
    - "All" filter sentinel changed from `undefined` to `''` since
      USelect v3 doesn't reliably clear on an undefined item value.

  STILL UNCONFIRMED against your actual repo. If your app is NOT on
  Nuxt UI v3, or uses different item-shape conventions, this needs
  another pass — ideally against a real working page from your app
  (e.g. patients/frontend/pages/*.vue) that uses UModal + USelect.
-->
<script setup lang="ts">
import { PERMISSIONS } from '~/config/permissions'
import type { Medication, MedicationInput } from '../../composables/useMedications'

const { t } = useI18n()
const { can } = usePermissions()
const { list, create, update, remove } = useMedications()

const medications = ref<Medication[]>([])
const loading = ref(false)

const searchName = ref('')
const filterForm = ref<string>('')
const filterStatus = ref<string>('') // '', 'true', 'false'

const formOptions = [
  'tablet', 'capsule', 'syrup', 'gel', 'mouthwash', 'injection', 'cream', 'other',
] as const
const unitOptions = ['mg', 'g', 'ml', 'UI', '%', 'other'] as const

const formFilterItems = computed(() => [
  { label: t('medications.filters.all'), value: '' },
  ...formOptions.map((f) => ({ label: t(`medications.form.${f}`), value: f })),
])

const statusFilterItems = computed(() => [
  { label: t('medications.filters.all'), value: '' },
  { label: t('medications.status.active'), value: 'true' },
  { label: t('medications.status.inactive'), value: 'false' },
])

const formSelectItems = computed(() =>
  formOptions.map((f) => ({ label: t(`medications.form.${f}`), value: f })),
)
const unitSelectItems = computed(() =>
  unitOptions.map((u) => ({ label: t(`medications.unit.${u}`), value: u })),
)

const fetchMedications = async () => {
  loading.value = true
  try {
    const res = await list({
      name: searchName.value || undefined,
      form: (filterForm.value || undefined) as Medication['form'] | undefined,
      is_prescribed: filterStatus.value === '' ? undefined : filterStatus.value === 'true',
    })
    medications.value = res.data
  } finally {
    loading.value = false
  }
}

let debounceHandle: ReturnType<typeof setTimeout> | undefined
watch(searchName, () => {
  if (debounceHandle) clearTimeout(debounceHandle)
  debounceHandle = setTimeout(fetchMedications, 300)
})
watch([filterForm, filterStatus], fetchMedications)
onMounted(fetchMedications)

const emptyDraft = (): MedicationInput => ({
  name: '',
  dose: 0,
  unit: 'mg',
  form: 'tablet',
  times_per_day: null,
  instructions: null,
  is_prescribed: true,
})

const isModalOpen = ref(false)
const editingId = ref<string | null>(null)
const draft = reactive<MedicationInput>(emptyDraft())
const saving = ref(false)

const openCreate = () => {
  editingId.value = null
  Object.assign(draft, emptyDraft())
  isModalOpen.value = true
}

const openEdit = (medication: Medication) => {
  editingId.value = medication.id
  Object.assign(draft, {
    name: medication.name,
    dose: medication.dose,
    unit: medication.unit,
    form: medication.form,
    times_per_day: medication.times_per_day,
    instructions: medication.instructions,
    is_prescribed: medication.is_prescribed,
  })
  isModalOpen.value = true
}

const save = async () => {
  saving.value = true
  try {
    if (editingId.value) {
      await update(editingId.value, draft)
    } else {
      await create(draft)
    }
    isModalOpen.value = false
    await fetchMedications()
  } finally {
    saving.value = false
  }
}

const isDeleteModalOpen = ref(false)
const confirmingDeleteId = ref<string | null>(null)

const askDelete = (id: string) => {
  confirmingDeleteId.value = id
  isDeleteModalOpen.value = true
}

const doDelete = async () => {
  if (!confirmingDeleteId.value) return
  await remove(confirmingDeleteId.value)
  isDeleteModalOpen.value = false
  confirmingDeleteId.value = null
  await fetchMedications()
}
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-xl font-semibold">{{ t('medications.title') }}</h1>
      <UButton
        v-if="can(PERMISSIONS.medications.write)"
        icon="i-lucide-plus"
        @click="openCreate"
      >
        {{ t('medications.actions.add') }}
      </UButton>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <UInput
        v-model="searchName"
        icon="i-lucide-search"
        :placeholder="t('medications.search')"
        class="w-64"
      />
      <USelect
        v-model="filterForm"
        :items="formFilterItems"
        :placeholder="t('medications.filters.form')"
        class="w-48"
      />
      <USelect
        v-model="filterStatus"
        :items="statusFilterItems"
        :placeholder="t('medications.filters.active')"
        class="w-48"
      />
    </div>

    <table class="w-full text-sm border-collapse">
      <thead>
        <tr class="border-b">
          <th class="text-left p-2">{{ t('medications.table.name') }}</th>
          <th class="text-left p-2">{{ t('medications.table.dose') }}</th>
          <th class="text-left p-2">{{ t('medications.table.form') }}</th>
          <th class="text-left p-2">{{ t('medications.table.regimen') }}</th>
          <th class="text-left p-2">{{ t('medications.table.status') }}</th>
          <th v-if="can(PERMISSIONS.medications.write)" class="text-right p-2">
            {{ t('medications.table.actions') }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td colspan="6" class="p-4 text-center text-gray-400">...</td>
        </tr>
        <tr v-else-if="medications.length === 0">
          <td colspan="6" class="p-4 text-center text-gray-400">
            {{ t('medications.empty') }}
          </td>
        </tr>
        <tr v-for="med in medications" :key="med.id" class="border-b">
          <td class="p-2">{{ med.name }}</td>
          <td class="p-2">{{ med.dose }} {{ t(`medications.unit.${med.unit}`) }}</td>
          <td class="p-2">{{ t(`medications.form.${med.form}`) }}</td>
          <td class="p-2">
            <span v-if="med.times_per_day">{{ med.times_per_day }}x/day</span>
            <span v-if="med.instructions" class="text-gray-400 ml-1">{{ med.instructions }}</span>
          </td>
          <td class="p-2">
            <UBadge :color="med.is_prescribed ? 'success' : 'neutral'">
              {{ t(med.is_prescribed ? 'medications.status.active' : 'medications.status.inactive') }}
            </UBadge>
          </td>
          <td v-if="can(PERMISSIONS.medications.write)" class="p-2 text-right space-x-2">
            <UButton size="xs" variant="ghost" icon="i-lucide-pencil" @click="openEdit(med)" />
            <UButton
              size="xs"
              variant="ghost"
              color="error"
              icon="i-lucide-trash-2"
              @click="askDelete(med.id)"
            />
          </td>
        </tr>
      </tbody>
    </table>

    <UModal v-model:open="isModalOpen">
      <template #content>
        <div class="p-4 space-y-3">
          <h2 class="text-lg font-semibold">
            {{ editingId ? t('medications.actions.edit') : t('medications.actions.add') }}
          </h2>

          <UFormField :label="t('medications.fields.name')">
            <UInput v-model="draft.name" class="w-full" />
          </UFormField>

          <div class="flex gap-3">
            <UFormField :label="t('medications.fields.dose')" class="flex-1">
              <UInput v-model.number="draft.dose" type="number" min="0" step="0.01" class="w-full" />
            </UFormField>
            <UFormField :label="t('medications.fields.unit')" class="flex-1">
              <USelect v-model="draft.unit" :items="unitSelectItems" class="w-full" />
            </UFormField>
          </div>

          <UFormField :label="t('medications.fields.form')">
            <USelect v-model="draft.form" :items="formSelectItems" class="w-full" />
          </UFormField>

          <UFormField :label="t('medications.fields.timesPerDay')">
            <UInput v-model.number="draft.times_per_day" type="number" min="1" max="24" class="w-full" />
          </UFormField>

          <UFormField :label="t('medications.fields.instructions')">
            <UTextarea v-model="draft.instructions" class="w-full" />
          </UFormField>

          <UFormField :label="t('medications.fields.isPrescribed')">
            <USwitch v-model="draft.is_prescribed" />
          </UFormField>

          <div class="flex justify-end gap-2 pt-2">
            <UButton variant="ghost" @click="isModalOpen = false">
              {{ t('medications.actions.cancel') }}
            </UButton>
            <UButton :loading="saving" @click="save">
              {{ t('medications.actions.save') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <UModal v-model:open="isDeleteModalOpen">
      <template #content>
        <div class="p-4 space-y-4">
          <p>{{ t('medications.confirmDelete') }}</p>
          <div class="flex justify-end gap-2">
            <UButton variant="ghost" @click="isDeleteModalOpen = false">
              {{ t('medications.actions.cancel') }}
            </UButton>
            <UButton color="error" @click="doDelete">
              {{ t('medications.actions.delete') }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
