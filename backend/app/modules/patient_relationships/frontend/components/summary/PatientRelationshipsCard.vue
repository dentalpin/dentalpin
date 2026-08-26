<script setup lang="ts">
/**
 * PatientRelationshipsCard — family relationships (Lien de Parentée).
 *
 * Registered into `patient.summary.cards` by patient_relationships. Self-contained
 * (view + inline edit in one card) rather than deep-linking into the core
 * patient page's edit modal — see module docstring in __init__.py.
 *
 * Previously also showed a manually-entered exemption status; removed —
 * APCI is now a computed flag off systemic-disease reference data, which
 * will surface elsewhere once the reference-data work lands.
 */
import type { PatientExtended, Patient, PaginatedResponse } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const { can } = usePermissions()
// This card is self-mounted via the patient.summary.cards slot (see
// slots.client.ts), not hosted by a parent page the way patients_clinical's
// medical-history form is -- there's no patients/[id].vue computing a
// :can-edit prop to pass in, so the card checks its own write permission
// directly. The slot registration's `permission: 'patient_relationships.read'`
// already gates whether this card mounts at all; this is the finer-grained
// write gate for the controls inside it.
const canWrite = computed(() => can(PERMISSIONS.patientRelationships.write))
const patientId = computed(() => props.ctx.patient.id)
const { relationships, isLoading, isSaving, fetchAll, addRelationship, removeRelationship }
  = usePatientRelationships(patientId)

onMounted(fetchAll)

const isEditing = ref(false)

const relationshipTypeOptions = computed(() => [
  { value: 'parent', label: t('patientRelationships.relationships.types.parent') },
  { value: 'child', label: t('patientRelationships.relationships.types.child') },
  { value: 'spouse', label: t('patientRelationships.relationships.types.spouse') },
  { value: 'sibling', label: t('patientRelationships.relationships.types.sibling') },
  { value: 'guardian', label: t('patientRelationships.relationships.types.guardian') },
  { value: 'ward', label: t('patientRelationships.relationships.types.ward') },
  { value: 'other', label: t('patientRelationships.relationships.types.other') }
])

// Patient picker: UInputMenu with server-side search. The dropdown is
// teleported to <body> (Reka UI portal), so it isn't clipped by
// SummaryCard's overflow-hidden the way PatientSearch's inline
// absolute-positioned dropdown was.
interface PatientOption {
  label: string
  id: string
}

const api = useApi()
const newRelatedPatient = ref<PatientOption | undefined>(undefined)
const newRelationshipType = ref('other')
const searchTerm = ref('')
const searchResults = ref<PatientOption[]>([])
const isSearching = ref(false)
let searchTimeout: ReturnType<typeof setTimeout> | null = null

watch(searchTerm, (val) => {
  if (searchTimeout) clearTimeout(searchTimeout)
  if (val.length < 2) {
    searchResults.value = []
    return
  }
  searchTimeout = setTimeout(() => searchPatients(val), 300)
})

async function searchPatients(query: string) {
  isSearching.value = true
  try {
    const params = new URLSearchParams({ search: query, page: '1', page_size: '10' })
    const res = await api.get<PaginatedResponse<Patient>>(
      `/api/v1/patients?${params.toString()}`
    )
    searchResults.value = res.data
      .filter(p => p.id !== patientId.value)
      .map(p => ({ label: `${p.last_name}, ${p.first_name}`, id: p.id }))
  } catch {
    searchResults.value = []
  } finally {
    isSearching.value = false
  }
}

async function handleAddRelationship() {
  if (!newRelatedPatient.value) return
  const ok = await addRelationship({
    related_patient_id: newRelatedPatient.value.id,
    relationship_type: newRelationshipType.value
  })
  if (ok) {
    newRelatedPatient.value = undefined
    newRelationshipType.value = 'other'
    searchTerm.value = ''
    searchResults.value = []
  }
}

const visibleRelationships = computed(() => relationships.value.slice(0, 3))
const extraRelationshipsCount = computed(() =>
  Math.max(0, relationships.value.length - visibleRelationships.value.length)
)
</script>

<template>
  <SummaryCard
    :title="t('patientRelationships.title')"
    icon="i-lucide-users"
    severity="neutral"
    :loading="isLoading"
    :empty="relationships.length === 0 && !isEditing"
  >
    <template
      v-if="canWrite"
      #header-trailing
    >
      <UButton
        icon="i-lucide-pencil"
        :aria-label="t('common.edit')"
        variant="ghost"
        color="neutral"
        size="xs"
        class="ml-auto"
        @click="isEditing = !isEditing"
      />
    </template>

    <template #empty>
      {{ t('patientRelationships.emptyHint') }}
    </template>

    <ul
      v-if="!isEditing"
      class="space-y-0.5 text-caption"
    >
      <li
        v-for="r in visibleRelationships"
        :key="r.id"
        class="flex items-center gap-1.5 text-muted truncate"
      >
        <UIcon
          name="i-lucide-users"
          class="w-3.5 h-3.5 shrink-0 text-subtle"
        />
        <span class="text-subtle">{{ t(`patientRelationships.relationships.types.${r.relationship_type}`) }}:</span>
        <NuxtLink
          :to="`/patients/${r.related_patient_id}`"
          class="text-default truncate hover:text-primary-accent hover:underline"
        >
          {{ r.related_patient_name }}
        </NuxtLink>
      </li>
      <li
        v-if="extraRelationshipsCount > 0"
        class="text-subtle pl-5"
      >
        +{{ extraRelationshipsCount }}
      </li>
    </ul>

    <div
      v-else
      class="space-y-2"
    >
      <ul
        v-if="relationships.length > 0"
        class="space-y-1"
      >
        <li
          v-for="r in relationships"
          :key="r.id"
          class="flex items-center gap-1.5 text-caption"
        >
          <span class="text-subtle">{{ t(`patientRelationships.relationships.types.${r.relationship_type}`) }}:</span>
          <NuxtLink
            :to="`/patients/${r.related_patient_id}`"
            class="flex-1 truncate text-default hover:text-primary-accent hover:underline"
          >
            {{ r.related_patient_name }}
          </NuxtLink>
          <UButton
            v-if="canWrite"
            icon="i-lucide-x"
            :aria-label="t('common.remove')"
            variant="ghost"
            color="neutral"
            size="xs"
            @click="removeRelationship(r.id)"
          />
        </li>
      </ul>

      <div
        v-if="canWrite"
        class="flex flex-col gap-1.5"
      >
        <UInputMenu
          v-model="newRelatedPatient"
          v-model:search-term="searchTerm"
          :items="searchResults"
          :loading="isSearching"
          ignore-filter
          icon="i-lucide-search"
          size="sm"
          :placeholder="t('patientRelationships.relationships.searchPatient')"
        />
        <div class="flex gap-1.5">
          <USelect
            v-model="newRelationshipType"
            :items="relationshipTypeOptions"
            size="sm"
            class="flex-1"
          />
          <UButton
            icon="i-lucide-plus"
            :aria-label="t('common.add')"
            size="sm"
            :disabled="!newRelatedPatient"
            :loading="isSaving"
            @click="handleAddRelationship"
          />
        </div>
      </div>
    </div>
  </SummaryCard>
</template>
