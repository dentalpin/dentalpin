<script setup lang="ts">
/**
 * NoteCard — shared presentational card for a single clinical note.
 *
 * Renders the color-coded type badge, author + relative timestamp, body
 * (with a "show more" toggle for long entries) and optional linked-entity
 * chip. Edit/delete only render when the parent passes ``can-edit``.
 */

import type {
  ClinicalNoteAuthor,
  ClinicalNoteLinked,
  Document,
  NoteAttachment,
  NoteType
} from '~~/app/types'

const props = defineProps<{
  noteId: string
  noteType: NoteType
  body: string
  createdAt: string
  author: ClinicalNoteAuthor | { id: string; full_name?: string | null }
  linked?: ClinicalNoteLinked | null
  attachments?: NoteAttachment[]
  /** When true, edit/delete actions are visible. Computed by parent. */
  canEdit?: boolean
  /** Highlight the card (e.g. when matching the current selected tooth). */
  highlight?: boolean
}>()

const emit = defineEmits<{
  edit: []
  delete: []
  'open-linked': [linked: ClinicalNoteLinked]
}>()

const { t, locale } = useI18n()
const { metaFor } = useNoteTypeMeta()

const meta = computed(() => metaFor(props.noteType))
const expanded = ref(false)
const TRUNCATE_AT = 280

const isLong = computed(() => (props.body || '').length > TRUNCATE_AT)
const visibleBody = computed(() => {
  if (!isLong.value || expanded.value) return props.body
  return `${props.body.slice(0, TRUNCATE_AT)}…`
})

function formatRelative(iso: string): string {
  try {
    const then = new Date(iso).getTime()
    const now = Date.now()
    const diffSec = Math.round((now - then) / 1000)
    if (diffSec < 60) return t('clinicalNotes.time.justNow')
    const diffMin = Math.round(diffSec / 60)
    if (diffMin < 60) return t('clinicalNotes.time.minutesAgo', { n: diffMin })
    const diffH = Math.round(diffMin / 60)
    if (diffH < 24) return t('clinicalNotes.time.hoursAgo', { n: diffH })
    const diffD = Math.round(diffH / 24)
    if (diffD < 7) return t('clinicalNotes.time.daysAgo', { n: diffD })
    return new Date(iso).toLocaleDateString(locale.value)
  } catch {
    return iso
  }
}

function formatAbsolute(iso: string): string {
  try {
    return new Date(iso).toLocaleString(locale.value)
  } catch {
    return iso
  }
}

const authorLabel = computed(() => {
  const a = props.author as { full_name?: string | null; email?: string | null }
  return a?.full_name || a?.email || t('clinicalNotes.author.unknown')
})

const initials = computed(() => {
  const label = authorLabel.value
  return label
    .split(/\s+/)
    .map(w => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
})

// Split attachments: image-like get inline thumbs + click-to-lightbox.
// Anything else stays as a paperclip badge with the document title.
function isImageAttachment(att: NoteAttachment): boolean {
  return (
    !!att.thumb_url
    && (att.media_kind === 'photo' || att.media_kind === 'xray')
    && !!att.mime_type?.startsWith('image/')
  )
}

const imageAttachments = computed<NoteAttachment[]>(
  () => (props.attachments ?? []).filter(isImageAttachment)
)
const nonImageAttachments = computed<NoteAttachment[]>(
  () => (props.attachments ?? []).filter(a => !isImageAttachment(a))
)

// Build minimal Document objects so the shared media PhotoLightbox
// (clinical_notes already depends on media) can paginate through them.
const lightboxDocuments = computed<Document[]>(() =>
  imageAttachments.value.map(att => ({
    id: att.document_id,
    patient_id: '',
    document_type: 'other',
    title: att.title ?? '',
    description: undefined,
    original_filename: '',
    mime_type: att.mime_type ?? 'image/jpeg',
    file_size: 0,
    status: 'active',
    media_kind: (att.media_kind ?? 'photo') as Document['media_kind'],
    media_category: null,
    media_subtype: null,
    captured_at: null,
    paired_document_id: null,
    tags: [],
    uploaded_by: '',
    created_at: att.created_at,
    updated_at: att.created_at,
    thumb_url: att.thumb_url,
    medium_url: att.medium_url,
    full_url: att.full_url
  }))
)

// Auth-aware blob URLs for the inline thumbs (server requires bearer).
const config = useRuntimeConfig()
const auth = useAuth()
const apiBaseUrl = computed(() =>
  import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
)
const thumbBlobs = ref<Record<string, string>>({})

async function loadThumb(att: NoteAttachment) {
  if (!att.thumb_url || thumbBlobs.value[att.id]) return
  try {
    const blob = await $fetch<Blob>(att.thumb_url, {
      baseURL: apiBaseUrl.value,
      headers: { Authorization: `Bearer ${auth.accessToken.value}` },
      responseType: 'blob'
    })
    thumbBlobs.value[att.id] = URL.createObjectURL(blob)
  } catch { /* swallow — falls back to icon placeholder */ }
}

watch(
  imageAttachments,
  list => { for (const a of list) loadThumb(a) },
  { immediate: true }
)

onBeforeUnmount(() => {
  for (const url of Object.values(thumbBlobs.value)) URL.revokeObjectURL(url)
})

const lightboxOpen = ref(false)
const lightboxStartId = ref<string | null>(null)

function openLightbox(att: NoteAttachment) {
  lightboxStartId.value = att.document_id
  lightboxOpen.value = true
}

const linkedLabel = computed(() => {
  const linked = props.linked
  if (!linked) return null
  if (linked.kind === 'patient' && linked.tooth_number) {
    return t('clinicalNotes.linked.tooth', { n: linked.tooth_number })
  }
  if (linked.kind === 'treatment') {
    if (linked.tooth_number && linked.label) {
      return t('clinicalNotes.linked.treatmentOnTooth', {
        label: linked.label,
        n: linked.tooth_number
      })
    }
    return linked.label || t('clinicalNotes.linked.treatment')
  }
  if (linked.kind === 'plan') {
    return linked.label
      ? t('clinicalNotes.linked.planNamed', { label: linked.label })
      : t('clinicalNotes.linked.plan')
  }
  return null
})
</script>

<template>
  <article
    class="note-card group relative border rounded-token-md p-3 bg-surface transition-colors"
    :class="[
      `note-card--${noteType}`,
      highlight ? 'ring-2 ring-primary' : 'border-default'
    ]"
    :data-note-id="noteId"
  >
    <header class="flex items-start gap-2">
      <UAvatar
        size="xs"
        :alt="authorLabel"
      >
        <span class="text-caption font-semibold">{{ initials }}</span>
      </UAvatar>
      <div class="flex-1 min-w-0">
        <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span class="font-medium text-sm truncate">{{ authorLabel }}</span>
          <UBadge
            :color="meta.color"
            variant="subtle"
            size="xs"
            class="shrink-0"
          >
            <UIcon
              :name="meta.icon"
              class="w-3 h-3 mr-1"
            />
            {{ t(meta.labelKey) }}
          </UBadge>
          <span
            v-if="linkedLabel"
            class="text-caption text-muted truncate"
          >
            · {{ linkedLabel }}
          </span>
        </div>
        <span
          class="text-caption text-subtle"
          :title="formatAbsolute(createdAt)"
        >
          {{ formatRelative(createdAt) }}
        </span>
      </div>
      <div
        v-if="canEdit"
        class="flex gap-1 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition"
      >
        <UButton
          icon="i-lucide-pencil"
          size="xs"
          variant="ghost"
          :aria-label="t('actions.edit')"
          @click="emit('edit')"
        />
        <UButton
          icon="i-lucide-trash-2"
          size="xs"
          variant="ghost"
          color="error"
          :aria-label="t('actions.delete')"
          @click="emit('delete')"
        />
      </div>
    </header>

    <div class="mt-2 text-sm whitespace-pre-wrap break-words">
      {{ visibleBody }}
    </div>

    <button
      v-if="isLong"
      type="button"
      class="mt-1 text-caption text-primary hover:underline"
      @click="expanded = !expanded"
    >
      {{ expanded ? t('clinicalNotes.actions.showLess') : t('clinicalNotes.actions.showMore') }}
    </button>

    <!-- Image attachments: thumbnail grid that opens the shared lightbox. -->
    <div
      v-if="imageAttachments.length"
      class="mt-2 flex flex-wrap gap-1.5 relative z-10"
    >
      <button
        v-for="att in imageAttachments"
        :key="att.id"
        type="button"
        class="group relative h-16 w-16 overflow-hidden rounded border border-default bg-elevated transition hover:ring-2 hover:ring-primary focus:outline-none focus:ring-2 focus:ring-primary"
        :title="att.title ?? ''"
        @click.stop="openLightbox(att)"
      >
        <img
          v-if="thumbBlobs[att.id]"
          :src="thumbBlobs[att.id]"
          :alt="att.title ?? ''"
          class="h-full w-full object-cover"
        >
        <UIcon
          v-else
          name="i-lucide-image"
          class="absolute inset-0 m-auto h-5 w-5 text-muted"
        />
      </button>
    </div>

    <!-- Non-image attachments: small file pill (no preview). -->
    <div
      v-if="nonImageAttachments.length"
      class="mt-2 flex flex-wrap gap-1 relative z-10"
    >
      <a
        v-for="att in nonImageAttachments"
        :key="att.id"
        :href="att.full_url ?? '#'"
        target="_blank"
        rel="noopener"
        class="inline-flex items-center gap-1 rounded bg-elevated px-2 py-0.5 text-caption text-muted hover:text-default hover:bg-default"
        @click.stop
      >
        <UIcon
          :name="att.mime_type === 'application/pdf' ? 'i-lucide-file-text' : 'i-lucide-paperclip'"
          class="h-3 w-3"
        />
        {{ att.title ?? att.document_id.slice(0, 8) }}
      </a>
    </div>

    <PhotoLightbox
      v-if="imageAttachments.length"
      v-model:open="lightboxOpen"
      :documents="lightboxDocuments"
      :start-id="lightboxStartId"
    />

    <button
      v-if="linked && linked.id"
      type="button"
      class="absolute inset-0 rounded-token-md focus:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      :aria-label="t('clinicalNotes.actions.openLinked')"
      @click="emit('open-linked', linked!)"
    />
  </article>
</template>

<style scoped>
.note-card {
  position: relative;
}

.note-card--administrative,
.note-card--appointment_administrative {
  border-left: 3px solid var(--color-neutral, #94a3b8);
}
.note-card--diagnosis,
.note-card--appointment_clinical {
  border-left: 3px solid var(--color-info-accent, #3b82f6);
}
.note-card--treatment {
  border-left: 3px solid var(--color-success-accent, #22c55e);
}
.note-card--treatment_plan {
  border-left: 3px solid var(--color-secondary-accent, #a855f7);
}

/* The full-card link button must stay underneath interactive children. */
.note-card button[aria-label]:last-child {
  z-index: 0;
}
.note-card > header,
.note-card > div,
.note-card > button[type='button']:not(:last-child) {
  position: relative;
  z-index: 1;
}
</style>
