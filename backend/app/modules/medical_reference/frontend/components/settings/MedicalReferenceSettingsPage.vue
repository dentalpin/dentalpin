<script setup lang="ts">
import type {
  ReferenceContraindication,
  ReferenceInteraction,
  ReferenceItem,
  ReferenceKind
} from '../../composables/useMedicalReference'

type Tab = ReferenceKind | 'interactions' | 'contraindications'

const { t } = useI18n()
const {
  search,
  create,
  deactivate,
  listInteractions,
  createInteraction,
  deactivateInteraction,
  listContraindications,
  createContraindication,
  deactivateContraindication
} = useMedicalReference()

const tabs = [
  { value: 'allergies' as Tab, label: t('medicalReference.tabs.allergies') },
  { value: 'medications' as Tab, label: t('medicalReference.tabs.medications') },
  { value: 'diseases' as Tab, label: t('medicalReference.tabs.diseases') },
  { value: 'surgeries' as Tab, label: t('medicalReference.tabs.surgeries') },
  { value: 'interactions' as Tab, label: t('medicalReference.tabs.interactions') },
  { value: 'contraindications' as Tab, label: t('medicalReference.tabs.contraindications') }
]
const activeTab = ref<Tab>('allergies')
const isNameListTab = computed(() =>
  ['allergies', 'medications', 'diseases', 'surgeries'].includes(activeTab.value)
)

// --- Simple name lists (allergies/medications/diseases/surgeries) --------

const items = ref<ReferenceItem[]>([])
const loading = ref(false)
const includeInactive = ref(false)

async function loadNameList() {
  if (!isNameListTab.value) return
  loading.value = true
  try {
    items.value = await search(activeTab.value as ReferenceKind, '', includeInactive.value, 1000)
  } finally {
    loading.value = false
  }
}

const newName = ref('')
const newIsApci = ref(false)
const saving = ref(false)

async function handleAddName() {
  if (!newName.value.trim()) return
  saving.value = true
  try {
    const data: { name: string, is_apci?: boolean } = { name: newName.value.trim() }
    if (activeTab.value === 'diseases') data.is_apci = newIsApci.value
    const created = await create(activeTab.value as ReferenceKind, data)
    if (created) {
      items.value.push(created)
      newName.value = ''
      newIsApci.value = false
    }
  } finally {
    saving.value = false
  }
}

async function handleDeactivateName(id: string) {
  const ok = await deactivate(activeTab.value as ReferenceKind, id)
  if (ok) await loadNameList()
}

// --- Interactions ----------------------------------------------------------

const interactions = ref<ReferenceInteraction[]>([])
const interactionMedA = ref<string | null>(null)
const interactionMedAName = ref('')
const interactionMedB = ref<string | null>(null)
const interactionMedBName = ref('')
const interactionNote = ref('')

async function loadInteractions() {
  loading.value = true
  try {
    interactions.value = await listInteractions(includeInactive.value)
  } finally {
    loading.value = false
  }
}

async function handleAddInteraction() {
  if (!interactionMedA.value || !interactionMedB.value || !interactionNote.value.trim()) return
  saving.value = true
  try {
    const created = await createInteraction({
      medication_a_id: interactionMedA.value,
      medication_b_id: interactionMedB.value,
      risk_note: interactionNote.value.trim()
    })
    if (created) {
      interactions.value.push(created)
      interactionMedA.value = null
      interactionMedAName.value = ''
      interactionMedB.value = null
      interactionMedBName.value = ''
      interactionNote.value = ''
    }
  } finally {
    saving.value = false
  }
}

async function handleDeactivateInteraction(id: string) {
  const ok = await deactivateInteraction(id)
  if (ok) await loadInteractions()
}

// --- Contraindications ------------------------------------------------------

const contraindications = ref<ReferenceContraindication[]>([])
const contraDisease = ref<string | null>(null)
const contraDiseaseName = ref('')
const contraMedication = ref<string | null>(null)
const contraMedicationName = ref('')
const contraNote = ref('')

async function loadContraindications() {
  loading.value = true
  try {
    contraindications.value = await listContraindications(includeInactive.value)
  } finally {
    loading.value = false
  }
}

async function handleAddContraindication() {
  if (!contraDisease.value || !contraMedication.value || !contraNote.value.trim()) return
  saving.value = true
  try {
    const created = await createContraindication({
      disease_id: contraDisease.value,
      medication_id: contraMedication.value,
      risk_note: contraNote.value.trim()
    })
    if (created) {
      contraindications.value.push(created)
      contraDisease.value = null
      contraDiseaseName.value = ''
      contraMedication.value = null
      contraMedicationName.value = ''
      contraNote.value = ''
    }
  } finally {
    saving.value = false
  }
}

async function handleDeactivateContraindication(id: string) {
  const ok = await deactivateContraindication(id)
  if (ok) await loadContraindications()
}

// --- Tab switching -----------------------------------------------------------

async function loadActiveTab() {
  if (activeTab.value === 'interactions') await loadInteractions()
  else if (activeTab.value === 'contraindications') await loadContraindications()
  else await loadNameList()
}

onMounted(loadActiveTab)
watch([activeTab, includeInactive], loadActiveTab)
</script>

<template>
  <UCard>
    <div class="space-y-4">
      <UTabs
        v-model="activeTab"
        :items="tabs"
      />

      <div class="flex items-center justify-between">
        <UCheckbox
          v-model="includeInactive"
          :label="t('medicalReference.showInactive')"
        />
        <span class="text-caption text-subtle">
          {{
            t('medicalReference.itemCount', {
              count: isNameListTab
                ? items.length
                : activeTab === 'interactions'
                  ? interactions.length
                  : contraindications.length
            })
          }}
        </span>
      </div>

      <!-- Simple name lists -->
      <template v-if="isNameListTab">
        <UTable
          :data="items"
          :loading="loading"
          :columns="[
            { accessorKey: 'name', header: t('medicalReference.name') },
            ...(activeTab === 'diseases' ? [{ accessorKey: 'is_apci', header: 'APCI' }] : []),
            { accessorKey: 'is_active', header: t('medicalReference.status') },
            { accessorKey: 'actions', header: '' }
          ]"
        >
          <template #is_apci-cell="{ row }">
            <UBadge
              v-if="row.original.is_apci"
              color="info"
              size="xs"
            >
              APCI
            </UBadge>
          </template>
          <template #is_active-cell="{ row }">
            <UBadge
              :color="row.original.is_active ? 'success' : 'neutral'"
              variant="subtle"
              size="xs"
            >
              {{ row.original.is_active ? t('medicalReference.active') : t('medicalReference.inactive') }}
            </UBadge>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              v-if="row.original.is_active"
              icon="i-lucide-eye-off"
              variant="ghost"
              color="neutral"
              size="xs"
              @click="handleDeactivateName(row.original.id)"
            />
          </template>
        </UTable>

        <div class="flex gap-2 items-center pt-2 border-t border-subtle">
          <UInput
            v-model="newName"
            :placeholder="t('medicalReference.newItemPlaceholder')"
            class="flex-1"
          />
          <UCheckbox
            v-if="activeTab === 'diseases'"
            v-model="newIsApci"
            label="APCI"
          />
          <UButton
            icon="i-lucide-plus"
            :loading="saving"
            :disabled="!newName.trim()"
            @click="handleAddName"
          >
            {{ t('common.add') }}
          </UButton>
        </div>
      </template>

      <!-- Interactions: medication + medication pairs -->
      <template v-else-if="activeTab === 'interactions'">
        <UTable
          :data="interactions"
          :loading="loading"
          :columns="[
            { accessorKey: 'medication_a_name', header: t('medicalReference.medicationA') },
            { accessorKey: 'medication_b_name', header: t('medicalReference.medicationB') },
            { accessorKey: 'risk_note', header: t('medicalReference.riskNote') },
            { accessorKey: 'is_active', header: t('medicalReference.status') },
            { accessorKey: 'actions', header: '' }
          ]"
        >
          <template #is_active-cell="{ row }">
            <UBadge
              :color="row.original.is_active ? 'success' : 'neutral'"
              variant="subtle"
              size="xs"
            >
              {{ row.original.is_active ? t('medicalReference.active') : t('medicalReference.inactive') }}
            </UBadge>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              v-if="row.original.is_active"
              icon="i-lucide-eye-off"
              variant="ghost"
              color="neutral"
              size="xs"
              @click="handleDeactivateInteraction(row.original.id)"
            />
          </template>
        </UTable>

        <div class="space-y-2 pt-2 border-t border-subtle">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            <ReferenceSearchInput
              v-model="interactionMedAName"
              v-model:reference-id="interactionMedA"
              kind="medications"
              :placeholder="t('medicalReference.medicationA')"
            />
            <ReferenceSearchInput
              v-model="interactionMedBName"
              v-model:reference-id="interactionMedB"
              kind="medications"
              :placeholder="t('medicalReference.medicationB')"
            />
          </div>
          <div class="flex gap-2">
            <UInput
              v-model="interactionNote"
              :placeholder="t('medicalReference.riskNotePlaceholder')"
              class="flex-1"
            />
            <UButton
              icon="i-lucide-plus"
              :loading="saving"
              :disabled="!interactionMedA || !interactionMedB || !interactionNote.trim()"
              @click="handleAddInteraction"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
        </div>
      </template>

      <!-- Contraindications: disease + medication pairs -->
      <template v-else-if="activeTab === 'contraindications'">
        <UTable
          :data="contraindications"
          :loading="loading"
          :columns="[
            { accessorKey: 'disease_name', header: t('medicalReference.tabs.diseases') },
            { accessorKey: 'medication_name', header: t('medicalReference.tabs.medications') },
            { accessorKey: 'risk_note', header: t('medicalReference.riskNote') },
            { accessorKey: 'is_active', header: t('medicalReference.status') },
            { accessorKey: 'actions', header: '' }
          ]"
        >
          <template #is_active-cell="{ row }">
            <UBadge
              :color="row.original.is_active ? 'success' : 'neutral'"
              variant="subtle"
              size="xs"
            >
              {{ row.original.is_active ? t('medicalReference.active') : t('medicalReference.inactive') }}
            </UBadge>
          </template>
          <template #actions-cell="{ row }">
            <UButton
              v-if="row.original.is_active"
              icon="i-lucide-eye-off"
              variant="ghost"
              color="neutral"
              size="xs"
              @click="handleDeactivateContraindication(row.original.id)"
            />
          </template>
        </UTable>

        <div class="space-y-2 pt-2 border-t border-subtle">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
            <ReferenceSearchInput
              v-model="contraDiseaseName"
              v-model:reference-id="contraDisease"
              kind="diseases"
              :placeholder="t('medicalReference.tabs.diseases')"
            />
            <ReferenceSearchInput
              v-model="contraMedicationName"
              v-model:reference-id="contraMedication"
              kind="medications"
              :placeholder="t('medicalReference.tabs.medications')"
            />
          </div>
          <div class="flex gap-2">
            <UInput
              v-model="contraNote"
              :placeholder="t('medicalReference.riskNotePlaceholder')"
              class="flex-1"
            />
            <UButton
              icon="i-lucide-plus"
              :loading="saving"
              :disabled="!contraDisease || !contraMedication || !contraNote.trim()"
              @click="handleAddContraindication"
            >
              {{ t('common.add') }}
            </UButton>
          </div>
        </div>
      </template>
    </div>
  </UCard>
</template>
