<script setup lang="ts">
/**
 * ReferenceSearchInput — searchable dropdown backed by a medical_reference
 * lookup list, with free-text fallback (Nuxt UI's `create-item="always"`).
 *
 * Consumed cross-module by patients_clinical's MedicalHistoryForm.vue —
 * auto-imported via Nuxt layer merging, same as PatientSearch is consumed
 * by lab_orders, no import statement needed on the consuming side.
 *
 * v-model is the plain text name (so a consumer that ignores reference-id
 * entirely still gets identical behavior to the old UInput). reference-id
 * is a second, optional v-model — null whenever the value was typed free
 * text rather than picked from the list.
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

const { search } = useMedicalReference()

const items = ref<ReferenceItem[]>([])
const isLoading = ref(false)

onMounted(async () => {
  isLoading.value = true
  items.value = await search(props.kind, '')
  isLoading.value = false
})

// Internal model is the full {id, name} object (or null) — USelectMenu's
// v-model reflects whichever item is selected/created.
const selected = computed<ReferenceItem | null>({
  get() {
    if (!props.modelValue) return null
    if (props.referenceId) {
      return items.value.find(i => i.id === props.referenceId) ?? { id: props.referenceId, name: props.modelValue, is_active: true }
    }
    return { id: '__free_text__', name: props.modelValue, is_active: true }
  },
  set(item) {
    if (!item) {
      emit('update:modelValue', '')
      emit('update:referenceId', null)
      return
    }
    emit('update:modelValue', item.name)
    emit('update:referenceId', item.id === '__free_text__' ? null : item.id)
  }
})

function handleCreate(name: string) {
  const trimmed = name.trim()
  if (!trimmed) return
  selected.value = { id: '__free_text__', name: trimmed, is_active: true }
}
</script>

<template>
  <USelectMenu
    v-model="selected"
    :items="items"
    :loading="isLoading"
    label-key="name"
    create-item="always"
    searchable
    :placeholder="placeholder"
    @create="handleCreate"
  />
</template>
