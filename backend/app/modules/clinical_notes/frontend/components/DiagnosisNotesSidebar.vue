<script setup lang="ts">
/**
 * DiagnosisNotesSidebar — right rail of the odontogram diagnosis screen.
 *
 * Diagnosis-only: every note created here is a ``diagnosis`` note tied to
 * the patient (and optionally to whatever tooth is currently selected in
 * the odontogram, passed via slot ctx). Treatment notes live in the
 * treatment-plan UI; administrative notes live in the patient Summary feed.
 *
 * Mounted via the ``odontogram.diagnosis.sidebar`` slot.
 */

import type { RecentNoteEntry } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  ctx: {
    patientId: string
    selectedTooth?: number | null
    /**
     * Host-supplied lookup so a treatment-owned note can be resolved to
     * the teeth it belongs to without this module importing odontogram.
     */
    treatmentsToothById?: Record<string, number[]>
    /** Host-supplied callback invoked on note hover/focus. */
    onTeethHover?: (teeth: number[] | null) => void
  }
}>()

const { t } = useI18n()
const { can } = usePermissions()
const {
  listRecentForPatient,
  createNote,
  updateNote,
  deleteNote
} = useClinicalNotes()
const { user } = useAuth()

const PAGE_SIZE = 20
const entries = ref<RecentNoteEntry[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const hasMore = ref(false)
const composerOpen = ref(true)
const composerRef = ref<{ reset: () => void } | null>(null)
const editingId = ref<string | null>(null)
const composerBody = ref('')
const saving = ref(false)

const canRead = computed(() => can(PERMISSIONS.clinicalNotes.read))
const canWrite = computed(() => can(PERMISSIONS.clinicalNotes.write))

const composerToothNumber = computed(() => props.ctx?.selectedTooth ?? null)

async function refresh() {
  if (!props.ctx?.patientId || !canRead.value) return
  loading.value = true
  try {
    // List shows every note type with its color code; only the composer
    // is diagnosis-only.
    const fetched = await listRecentForPatient(props.ctx.patientId, {
      limit: PAGE_SIZE
    })
    entries.value = fetched
    hasMore.value = fetched.length === PAGE_SIZE
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!props.ctx?.patientId || !canRead.value) return
  if (entries.value.length === 0) return
  loadingMore.value = true
  try {
    const before = entries.value[entries.value.length - 1]?.created_at
    const fetched = await listRecentForPatient(props.ctx.patientId, {
      limit: PAGE_SIZE,
      before
    })
    entries.value.push(...fetched)
    hasMore.value = fetched.length === PAGE_SIZE
  } finally {
    loadingMore.value = false
  }
}

function startEdit(entry: RecentNoteEntry) {
  editingId.value = entry.id
  composerBody.value = entry.body
  composerOpen.value = true
}

function startNew() {
  editingId.value = null
  composerBody.value = ''
  composerOpen.value = true
}

async function handleSubmit(payload: {
  body: string
  toothNumber: number | null
  attachmentDocumentIds: string[]
}) {
  if (!props.ctx?.patientId) return
  saving.value = true
  try {
    // The composable toasts on failure and returns null — keep the
    // draft (composer state) intact so the user can retry.
    const saved = editingId.value
      ? await updateNote(editingId.value, payload.body)
      : await createNote({
          note_type: 'diagnosis',
          owner_type: 'patient',
          owner_id: props.ctx.patientId,
          tooth_number: payload.toothNumber,
          body: payload.body,
          attachment_document_ids: payload.attachmentDocumentIds
        })
    if (!saved) return
    editingId.value = null
    composerBody.value = ''
    // The sidebar keeps the composer mounted, so clear the draft explicitly.
    composerRef.value?.reset()
    await refresh()
  } finally {
    saving.value = false
  }
}

async function handleDelete(entry: RecentNoteEntry) {
  // Destructive, no undo endpoint — same confirm the other note surfaces use.
  const confirmed = window.confirm(t('clinicalNotes.confirms.delete'))
  if (!confirmed) return
  const ok = await deleteNote(entry.id)
  if (ok) await refresh()
}

function canEditEntry(entry: RecentNoteEntry): boolean {
  return canWrite.value && !!entry.author?.id && entry.author.id === user.value?.id
}

// Resolve a note to the teeth it visually belongs to so hover/focus on a
// note row can pulse the matching tooth in the odontogram. Returns null
// when the note has no tooth (e.g. plan-level, administrative) so the
// host emits an empty highlight instead of a ghost pulse.
function resolveNoteTeeth(entry: RecentNoteEntry): number[] | null {
  if (entry.tooth_number != null) return [entry.tooth_number]
  if (entry.owner_type === 'treatment') {
    const teeth = props.ctx?.treatmentsToothById?.[entry.owner_id]
    if (teeth && teeth.length) return teeth
  }
  return null
}

function handleNoteEnter(entry: RecentNoteEntry) {
  const teeth = resolveNoteTeeth(entry)
  if (!teeth) return
  props.ctx?.onTeethHover?.(teeth)
}

function handleNoteLeave() {
  props.ctx?.onTeethHover?.(null)
}

watch(
  () => props.ctx?.patientId,
  refresh,
  { immediate: true }
)
</script>

<template>
  <aside
    v-if="canRead"
    class="diagnosis-notes-sidebar h-full flex flex-col gap-3 p-3 bg-surface-muted/50 rounded-token-lg"
  >
    <header class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2 min-w-0">
        <UIcon
          name="i-lucide-notebook-pen"
          class="w-5 h-5 text-info-accent shrink-0"
        />
        <h3 class="font-medium truncate">
          {{ t('clinicalNotes.diagnosisSidebar.title') }}
        </h3>
      </div>
      <UButton
        v-if="canWrite && !composerOpen"
        size="xs"
        variant="ghost"
        icon="i-lucide-plus"
        @click="startNew"
      >
        {{ t('clinicalNotes.diagnosisSidebar.addNote') }}
      </UButton>
    </header>

    <NoteComposer
      v-if="composerOpen && canWrite"
      ref="composerRef"
      note-type="diagnosis"
      :initial-body="composerBody"
      :tooth-number="composerToothNumber"
      :patient-id="props.ctx?.patientId"
      :busy="saving"
      @submit="handleSubmit"
      @cancel="composerOpen = false"
    />

    <div class="flex-1 overflow-y-auto pr-1 space-y-2">
      <div
        v-if="loading"
        class="space-y-2"
      >
        <USkeleton
          v-for="i in 3"
          :key="i"
          class="h-20 w-full"
        />
      </div>
      <div
        v-else-if="entries.length === 0"
        class="text-center py-6 text-subtle text-sm"
      >
        {{ t('clinicalNotes.diagnosisSidebar.empty') }}
      </div>
      <NoteCard
        v-for="entry in entries"
        :key="entry.id"
        :note-id="entry.id"
        :note-type="entry.note_type"
        :body="entry.body"
        :created-at="entry.created_at"
        :author="entry.author"
        :linked="entry.linked"
        :attachments="entry.attachments"
        :can-edit="canEditEntry(entry)"
        :highlight="ctx?.selectedTooth != null && ctx.selectedTooth === entry.tooth_number"
        @edit="startEdit(entry)"
        @delete="handleDelete(entry)"
        @mouseenter="handleNoteEnter(entry)"
        @mouseleave="handleNoteLeave()"
        @focusin="handleNoteEnter(entry)"
        @focusout="handleNoteLeave()"
      />

      <div
        v-if="hasMore && !loading"
        class="flex justify-center pt-2"
      >
        <UButton
          variant="ghost"
          size="sm"
          :loading="loadingMore"
          @click="loadMore"
        >
          {{ t('clinicalNotes.feed.loadMore') }}
        </UButton>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.diagnosis-notes-sidebar {
  min-height: 320px;
}
</style>
