<script setup lang="ts">
/**
 * VisitNotePanel - Edit the single visit-level clinical note bound to
 * `AppointmentTreatment.notes` (agenda module).
 *
 * One note per visit — no timeline. Uses PATCH on the agenda endpoint so
 * writes stay inside the module that owns the underlying row.
 */

import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  appointmentTreatmentId: string
  initialNotes: string | null
  readonly?: boolean
}>()

const emit = defineEmits<{
  saved: [notes: string]
}>()

const { t } = useI18n()
const { can } = usePermissions()
const api = useApi()
const toast = useToast()

const body = ref(props.initialNotes ?? '')
const saving = ref(false)

const canWrite = computed(() => !props.readonly && can(PERMISSIONS.clinicalNotes.write))

watch(
  () => props.initialNotes,
  (val) => {
    body.value = val ?? ''
  }
)

async function save() {
  if (!canWrite.value) return
  saving.value = true
  try {
    const next = body.value.trim()
    await api.patch(
      `/api/v1/agenda/appointment-treatments/${props.appointmentTreatmentId}`,
      { notes: next }
    )
    toast.add({ title: t('treatmentPlans.visitNote.saved'), color: 'success' })
    emit('saved', next)
  } catch (error) {
    console.error('Error saving visit note:', error)
    toast.add({ title: t('common.error'), color: 'error' })
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <h4 class="font-medium text-sm">
        {{ t('treatmentPlans.visitNote.title') }}
      </h4>
    </div>
    <textarea
      v-model="body"
      :rows="6"
      :disabled="!canWrite"
      :placeholder="t('treatmentPlans.visitNote.empty')"
      class="clinical-note-textarea"
    />
    <div
      v-if="canWrite"
      class="flex justify-end"
    >
      <UButton
        size="sm"
        color="primary"
        :loading="saving"
        @click="save"
      >
        {{ t('treatmentPlans.visitNote.save') }}
      </UButton>
    </div>
  </div>
</template>

<style scoped>
.clinical-note-textarea {
  display: block;
  width: 100%;
  min-height: 8rem;
  padding: 0.625rem 0.75rem;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius, 6px);
  background: var(--ui-bg);
  color: var(--ui-text);
  font: inherit;
  line-height: 1.5;
  resize: vertical;
}

.clinical-note-textarea:focus {
  outline: none;
  border-color: var(--ui-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ui-primary) 25%, transparent);
}

.clinical-note-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
