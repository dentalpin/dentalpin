<script setup lang="ts">
/**
 * ReferenceSearchInput — searchable dropdown backed by a medical_reference
 * lookup list. Typing something not in the list creates a new reference
 * item via the API (Nuxt UI's `create-item="always"`) rather than storing
 * loose free text — every entry from this component always ends up with a
 * real reference_id, which the interaction/contraindication active-check
 * depends on to reliably match a patient's medications/diseases. (Entries
 * created before this change still have reference_id = null; those are
 * simply excluded from the active check rather than guessed at — see
 * MedicalReferenceService.get_patient_flags.)
 *
 * Consumed cross-module by patients_clinical's MedicalHistoryForm.vue —
 * auto-imported via Nuxt layer merging, same as PatientSearch is consumed
 * by lab_orders, no import statement needed on the consuming side.
 */
import type { ReferenceItem, ReferenceKind } from '../composables/useMedicalReference'

const props = defineProps<{
  kind: ReferenceKind
  modelValue: string
  referenceId?: string | null
  placeholder?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  'update:referenceId': [value: string | null]
}>()

const { search, create } = useMedicalReference()

const items = ref<ReferenceItem[]>([])
const isLoading = ref(false)
const isCreating = ref(false)

onMounted(async () => {
  isLoading.value = true
  items.value = await search(props.kind, '')
  isLoading.value = false
})

const selected = computed<ReferenceItem | null>({
  get() {
    if (!props.referenceId) return null
    return items.value.find(i => i.id === props.referenceId) ?? { id: props.referenceId, name: props.modelValue, is_active: true }
  },
  set(item) {
    if (!item) {
      emit('update:modelValue', '')
      emit('update:referenceId', null)
      return
    }
    emit('update:modelValue', item.name)
    emit('update:referenceId', item.id)
  }
})

async function handleCreate(name: string) {
  const trimmed = name.trim()
  if (!trimmed) return
  isCreating.value = true
  const created = await create(props.kind, { name: trimmed })
  isCreating.value = false
  if (created) {
    items.value.push(created)
    selected.value = created
  }
  // create() already toasts on failure (e.g. name already exists) — leave
  // the field as-is rather than falling back to an unlinked free-text value.
}
</script>

<template>
  <USelectMenu
    v-model="selected"
    :items="items"
    :loading="isLoading || isCreating"
    label-key="name"
    create-item="always"
    searchable
    :placeholder="placeholder"
    @create="handleCreate"
  />
</template>
