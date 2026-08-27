<script setup lang="ts">
/**
 * AppointmentNotesPanel — clinical_notes UI mounted by the agenda
 * module's ``appointment.detail.notes`` slot.
 *
 * Owns the appointment-scoped notes feed: a composer with a
 * Clínica / Administrativa type selector at the top + a chronological
 * list of notes for the appointment (both types mixed, color-coded
 * by the shared NoteCard).
 *
 * Mounted from ``slots.client.ts``. ``agenda`` never imports this file —
 * the slot context is the only contract.
 */

import type { ClinicalNote, NoteType } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  ctx: { appointmentId: string, patientId?: string | null }
}>()

const { t } = useI18n()
const { can } = usePermissions()
const { listForOwner, createNote, updateNote, deleteNote } = useClinicalNotes()
const { user } = useAuth()
const { metaFor } = useNoteTypeMeta()

const APPOINTMENT_NOTE_TYPES: NoteType[] = [
  'appointment_clinical',
  'appointment_administrative'
]

const entries = ref<ClinicalNote[]>([])
const loading = ref(false)
const saving = ref(false)
const composerOpen = ref(false)
const composerType = ref<NoteType>('appointment_clinical')
const editingId = ref<string | null>(null)
const composerBody = ref('')

const canRead = computed(() => can(PERMISSIONS.clinicalNotes.read))
const canWrite = computed(() => can(PERMISSIONS.clinicalNotes.write))

const appointmentId = computed(() => props.ctx?.appointmentId)
const patientId = computed(() => props.ctx?.patientId ?? null)

async function refresh() {
  if (!appointmentId.value || !canRead.value) return
  loading.value = true
  try {
    entries.value = await listForOwner('appointment', appointmentId.value)
  } finally {
    loading.value = false
  }
}

function startNew(type: NoteType) {
  editingId.value = null
  composerType.value = type
  composerBody.value = ''
  composerOpen.value = true
}

function startEdit(entry: ClinicalNote) {
  editingId.value = entry.id
  composerType.value = entry.note_type
  composerBody.value = entry.body
  composerOpen.value = true
}

async function handleSubmit(
  payload: { body: string, toothNumber: number | null, attachmentDocumentIds: string[] }
) {
  if (!appointmentId.value) return
  saving.value = true
  try {
    // The composable toasts on failure and returns null — keep the
    // composer open with the draft intact so the user can retry.
    const saved = editingId.value
      ? await updateNote(editingId.value, payload.body)
      : await createNote({
          note_type: composerType.value,
          owner_type: 'appointment',
          owner_id: appointmentId.value,
          body: payload.body,
          attachment_document_ids: payload.attachmentDocumentIds
        })
    if (!saved) return
    composerOpen.value = false
    editingId.value = null
    composerBody.value = ''
    await refresh()
  } finally {
    saving.value = false
  }
}

async function handleDelete(entry: ClinicalNote) {
  const confirmed = window.confirm(t('clinicalNotes.confirms.delete'))
  if (!confirmed) return
  const ok = await deleteNote(entry.id)
  if (ok) await refresh()
}

function canEditEntry(entry: ClinicalNote): boolean {
  return canWrite.value && entry.author_id === user.value?.id
}

watch(appointmentId, refresh, { immediate: true })
</script>

<template>
  <section
    v-if="canRead"
    class="space-y-3"
  >
    <div
      v-if="canWrite && !composerOpen"
      class="flex flex-wrap gap-2"
    >
      <UButton
        v-for="type in APPOINTMENT_NOTE_TYPES"
        :key="type"
        size="sm"
        :color="metaFor(type).color"
        :icon="metaFor(type).icon"
        variant="soft"
        @click="startNew(type)"
      >
        {{ t('clinicalNotes.appointment.addByType', { label: t(metaFor(type).labelKey) }) }}
      </UButton>
    </div>

    <div v-if="composerOpen">
      <NoteComposer
        :note-type="composerType"
        :initial-body="composerBody"
        :patient-id="patientId"
        :busy="saving"
        autofocus
        @submit="handleSubmit"
        @cancel="composerOpen = false"
      />
    </div>

    <div
      v-if="loading"
      class="space-y-2"
    >
      <USkeleton
        v-for="i in 2"
        :key="i"
        class="h-20 w-full"
      />
    </div>

    <div
      v-else-if="entries.length === 0"
      class="text-center py-6 text-muted"
    >
      <UIcon
        name="i-lucide-notebook-pen"
        class="w-8 h-8 mx-auto mb-1.5 opacity-50"
      />
      <p class="text-sm">
        {{ t('clinicalNotes.appointment.empty') }}
      </p>
    </div>

    <ul
      v-else
      class="space-y-2"
    >
      <li
        v-for="entry in entries"
        :key="entry.id"
      >
        <NoteCard
          :note-id="entry.id"
          :note-type="entry.note_type"
          :body="entry.body"
          :created-at="entry.created_at"
          :author="entry.author ?? { id: entry.author_id }"
          :attachments="entry.attachments"
          :can-edit="canEditEntry(entry)"
          @edit="startEdit(entry)"
          @delete="handleDelete(entry)"
        />
      </li>
    </ul>
  </section>
</template>
