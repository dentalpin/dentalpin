<script setup lang="ts">
/**
 * PatientAdminCard — family relationships (Lien de Parentée).
 *
 * Registered into `patient.summary.cards` by patient_admin. Self-contained
 * (view + inline edit in one card) rather than deep-linking into the core
 * patient page's edit modal — see module docstring in __init__.py.
 *
 * Previously also showed a manually-entered exemption status; removed —
 * APCI is now a computed flag off systemic-disease reference data, which
 * will surface elsewhere once the reference-data work lands.
 */
import type { PatientExtended } from '~~/app/types'

interface Ctx {
  patient: PatientExtended
}

const props = defineProps<{ ctx: Ctx }>()

const { t } = useI18n()
const patientId = computed(() => props.ctx.patient.id)
const { relationships, isLoading, isSaving, fetchAll, addRelationship, removeRelationship } =
  usePatientAdmin(patientId)

onMounted(fetchAll)

const isEditing = ref(false)

const relationshipTypeOptions = computed(() => [
  { value: 'parent', label: t('patientAdmin.relationships.types.parent') },
  { value: 'child', label: t('patientAdmin.relationships.types.child') },
  { value: 'spouse', label: t('patientAdmin.relationships.types.spouse') },
  { value: 'sibling', label: t('patientAdmin.relationships.types.sibling') },
  { value: 'guardian', label: t('patientAdmin.relationships.types.guardian') },
  { value: 'ward', label: t('patientAdmin.relationships.types.ward') },
  { value: 'other', label: t('patientAdmin.relationships.types.other') }
])

const newRelatedPatient = ref<{ id: string, full_name?: string } | null>(null)
const newRelationshipType = ref('other')

async function handleAddRelationship() {
  if (!newRelatedPatient.value) return
  const ok = await addRelationship({
    related_patient_id: newRelatedPatient.value.id,
    relationship_type: newRelationshipType.value
  })
  if (ok) {
    newRelatedPatient.value = null
    newRelationshipType.value = 'other'
  }
}

const visibleRelationships = computed(() => relationships.value.slice(0, 3))
const extraRelationshipsCount = computed(() =>
  Math.max(0, relationships.value.length - visibleRelationships.value.length)
)
</script>

<template>
  <SummaryCard
    :title="t('patientAdmin.title')"
    icon="i-lucide-users"
    severity="neutral"
    :loading="isLoading"
    :empty="relationships.length === 0 && !isEditing"
  >
    <template #header-trailing>
      <UButton
        icon="i-lucide-pencil"
        variant="ghost"
        color="neutral"
        size="xs"
        class="ml-auto"
        @click="isEditing = !isEditing"
      />
    </template>

    <template #empty>
      {{ t('patientAdmin.emptyHint') }}
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
        <span class="text-subtle">{{ t(`patientAdmin.relationships.types.${r.relationship_type}`) }}:</span>
        <span class="text-default truncate">{{ r.related_patient_name }}</span>
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
          <span class="text-subtle">{{ t(`patientAdmin.relationships.types.${r.relationship_type}`) }}:</span>
          <span class="flex-1 truncate text-default">{{ r.related_patient_name }}</span>
          <UButton
            icon="i-lucide-x"
            variant="ghost"
            color="neutral"
            size="xs"
            @click="removeRelationship(r.id)"
          />
        </li>
      </ul>

      <div class="flex flex-col gap-1.5">
        <PatientSearch
          v-model="newRelatedPatient"
          :placeholder="t('patientAdmin.relationships.searchPatient')"
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
