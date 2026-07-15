<script setup lang="ts">
/**
 * NoteComposer — shared inline composer used by every note surface
 * (Summary feed, diagnosis sidebar, per-treatment popover, plan timeline).
 *
 * Owns the textarea + template picker + Save/Cancel buttons. Emits a single
 * ``submit`` payload. The parent decides where to write (note_type / owner).
 */

import type { Document, NoteTemplate, NoteType } from '~~/app/types'

const props = defineProps<{
  /** Initial body — pre-fills the textarea (use for edit, or clear with ''). */
  initialBody?: string
  /** Drives the template-category fetch. Pass the note_type that will be saved. */
  noteType: NoteType
  /** Override the static template-category fetch (e.g. clinical_type from odontogram). */
  templateCategory?: string
  /** Optional pre-bound tooth number for diagnosis notes. */
  toothNumber?: number | null
  /** Hide the tooth-binding checkbox even when noteType='diagnosis'. */
  hideToothBinding?: boolean
  /** When provided, enables the inline photo attachment uploader. */
  patientId?: string | null
  busy?: boolean
  autofocus?: boolean
}>()

const emit = defineEmits<{
  submit: [{ body: string; toothNumber: number | null; attachmentDocumentIds: string[] }]
  cancel: []
}>()

// Attachments — supports both clinical photos (image/*) and documents
// (PDFs). Photos go through the photo-aware endpoint so they land in
// the patient gallery; documents go through the document endpoint so
// they appear in the Documents tab. Both produce a Document row whose
// id we send up via ``attachmentDocumentIds``.
const { uploadPhoto, uploading: uploadingPhoto } = usePhotos()
const { uploadDocument, uploading: uploadingDoc } = useDocuments()
const attachedDocs = ref<Document[]>([])

const uploadingAttachment = computed(() => uploadingPhoto.value || uploadingDoc.value)

async function onFilesSelected(event: Event) {
  if (!props.patientId) return
  const input = event.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  for (const file of files) {
    const cleanTitle = file.name.replace(/\.[^.]+$/, '')
    if (file.type.startsWith('image/')) {
      const doc = await uploadPhoto(props.patientId, {
        file,
        title: cleanTitle,
        media_kind: 'photo',
        media_category: 'clinical',
        media_subtype: 'reference'
      })
      if (doc) attachedDocs.value.push(doc)
    } else {
      const doc = await uploadDocument(
        props.patientId,
        file,
        'other',
        cleanTitle
      )
      if (doc) attachedDocs.value.push(doc)
    }
  }
  input.value = ''
}

function removeAttached(id: string) {
  attachedDocs.value = attachedDocs.value.filter(d => d.id !== id)
}

function attachmentIcon(doc: Document): string {
  if (doc.media_kind === 'photo' || doc.media_kind === 'xray') return 'i-lucide-image'
  if (doc.mime_type === 'application/pdf') return 'i-lucide-file-text'
  return 'i-lucide-paperclip'
}

const { t, te } = useI18n()
const { metaFor } = useNoteTypeMeta()
const { listTemplates } = useClinicalNotes()

const meta = computed(() => metaFor(props.noteType))
const body = ref(props.initialBody ?? '')
const bindToTooth = ref(props.toothNumber !== null && props.toothNumber !== undefined)
const templates = ref<NoteTemplate[]>([])
const textareaRef = ref<HTMLTextAreaElement | null>(null)

const category = computed(() => props.templateCategory || meta.value.templateCategory)

watch(
  () => props.initialBody,
  (val) => {
    body.value = val ?? ''
  }
)
watch(
  () => props.toothNumber,
  (val) => {
    bindToTooth.value = val !== null && val !== undefined
  }
)

async function refreshTemplates() {
  templates.value = await listTemplates(category.value)
}

function applyTemplate(tpl: NoteTemplate) {
  const resolvedBody = te(tpl.body_i18n_key) ? t(tpl.body_i18n_key) : tpl.body
  if (body.value.trim()) {
    body.value = `${body.value.trim()}\n\n${resolvedBody}`
  } else {
    body.value = resolvedBody
  }
}

function handleSubmit() {
  const next = body.value.trim()
  if (!next || props.busy) return
  emit('submit', {
    body: next,
    toothNumber:
      props.noteType === 'diagnosis' && bindToTooth.value && props.toothNumber
        ? props.toothNumber
        : null,
    attachmentDocumentIds: attachedDocs.value.map(d => d.id)
  })
  attachedDocs.value = []
}

function handleCancel() {
  body.value = props.initialBody ?? ''
  attachedDocs.value = []
  emit('cancel')
}

onMounted(() => {
  refreshTemplates()
  if (props.autofocus) {
    nextTick(() => textareaRef.value?.focus())
  }
})

watch(category, refreshTemplates)
</script>

<template>
  <div class="note-composer space-y-2 border border-default rounded-token-md p-3 bg-surface">
    <div
      v-if="templates.length"
      class="flex flex-wrap gap-1 items-center"
    >
      <span class="text-caption text-muted mr-1">
        {{ t('clinicalNotes.composer.templates') }}:
      </span>
      <UButton
        v-for="tpl in templates"
        :key="tpl.id"
        size="xs"
        variant="ghost"
        @click="applyTemplate(tpl)"
      >
        {{ t(tpl.i18n_key) }}
      </UButton>
    </div>

    <textarea
      ref="textareaRef"
      v-model="body"
      :rows="6"
      :placeholder="t('clinicalNotes.composer.placeholder')"
      class="composer-textarea"
      :disabled="busy"
    />

    <!-- Inline attachments (photos + documents). Only when patientId is provided. -->
    <div
      v-if="patientId"
      class="space-y-1"
    >
      <div
        v-if="attachedDocs.length"
        class="flex flex-wrap gap-2"
      >
        <UBadge
          v-for="doc in attachedDocs"
          :key="doc.id"
          color="primary"
          variant="soft"
          class="cursor-default"
        >
          <UIcon
            :name="attachmentIcon(doc)"
            class="mr-1 h-3 w-3"
          />
          {{ doc.title }}
          <button
            type="button"
            class="ml-1"
            :aria-label="t('actions.remove')"
            @click="removeAttached(doc.id)"
          >
            <UIcon
              name="i-lucide-x"
              class="h-3 w-3"
            />
          </button>
        </UBadge>
      </div>
      <label
        class="inline-flex cursor-pointer items-center gap-1.5 rounded px-2 py-1 text-xs font-medium text-muted hover:bg-elevated hover:text-default"
        :class="{ 'pointer-events-none opacity-50': busy || uploadingAttachment }"
      >
        <UIcon
          v-if="!uploadingAttachment"
          name="i-lucide-paperclip"
          class="h-3.5 w-3.5"
        />
        <UIcon
          v-else
          name="i-lucide-loader-2"
          class="h-3.5 w-3.5 animate-spin"
        />
        <span>{{ t('clinicalNotes.composer.attach', 'Adjuntar foto o documento') }}</span>
        <input
          type="file"
          accept="image/*,application/pdf"
          multiple
          class="hidden"
          :disabled="busy || uploadingAttachment"
          @change="onFilesSelected"
        >
      </label>
    </div>

    <div class="flex flex-wrap items-center gap-2 justify-between">
      <label
        v-if="noteType === 'diagnosis' && !hideToothBinding && toothNumber"
        class="flex items-center gap-2 text-caption text-muted"
      >
        <UCheckbox
          v-model="bindToTooth"
          :disabled="busy"
        />
        <span>{{ t('clinicalNotes.composer.bindToTooth', { n: toothNumber }) }}</span>
      </label>
      <span v-else />

      <div class="flex gap-2">
        <UButton
          variant="ghost"
          size="sm"
          :disabled="busy"
          @click="handleCancel"
        >
          {{ t('actions.cancel') }}
        </UButton>
        <UButton
          color="primary"
          size="sm"
          :loading="busy"
          :disabled="!body.trim()"
          @click="handleSubmit"
        >
          {{ t('actions.save') }}
        </UButton>
      </div>
    </div>
  </div>
</template>

<style scoped>
.composer-textarea {
  display: block;
  width: 100%;
  min-height: 8rem;
  padding: 0.5rem 0.625rem;
  border: 1px solid var(--ui-border);
  border-radius: var(--ui-radius, 6px);
  background: var(--ui-bg);
  color: var(--ui-text);
  font: inherit;
  line-height: 1.5;
  resize: vertical;
}

.composer-textarea:focus {
  outline: none;
  border-color: var(--ui-primary);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--ui-primary) 25%, transparent);
}

.composer-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
