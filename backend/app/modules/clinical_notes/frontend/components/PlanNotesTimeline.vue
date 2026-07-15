<script setup lang="ts">
/**
 * PlanNotesTimeline — merged clinical-notes feed for a single plan.
 *
 * Shows plan-level + treatment-level + visit notes in one chronological list
 * with source badges. Plan-level notes are editable inline by their author;
 * treatment and visit entries are read-only here (treatment entries edit
 * via the TreatmentNoteButton; visit entries via VisitNotePanel in agenda).
 *
 * Drop-in replacement for the previous component that lived in
 * `treatment_plan` — same component name and prop signature so existing
 * imports (`<PlanNotesTimeline />`) keep resolving via Nuxt layer auto-discovery.
 */

import type { ClinicalNoteEntry, PlannedTreatmentItem, NoteType } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  planId: string
  /** Used to resolve treatment names for plan_item / visit entries. */
  items: PlannedTreatmentItem[]
  templateCategory?: string
  readonly?: boolean
  /** Enables the inline attachment uploader on the composer. */
  patientId?: string | null
}>()

const emit = defineEmits<{
  updated: []
  /**
   * Mirrors PlanTreatmentList's ``item-hover`` so the host can pulse
   * the matching tooth/arch on the odontogram when the user hovers a
   * note in the timeline. Plan-level notes emit ``null``.
   */
  'item-hover': [itemId: string | null]
}>()

const { t, locale } = useI18n()
const { user } = useAuth()
const { can } = usePermissions()
const { metaFor } = useNoteTypeMeta()
const {
  listMergedForPlan,
  createNote,
  updateNote,
  deleteNote
} = useClinicalNotes()

const entries = ref<ClinicalNoteEntry[]>([])
const loading = ref(false)
const composerOpen = ref(false)
const editingId = ref<string | null>(null)
const composerBody = ref('')
const saving = ref(false)

// Filter state — defaults to all sources so the merged feed shows plan +
// treatment + visit notes side-by-side.
type Source = 'plan' | 'treatment' | 'visit'
const ALL_SOURCES: Source[] = ['plan', 'treatment', 'visit']
const activeSources = ref<Set<Source>>(new Set(ALL_SOURCES))
const isAllSelected = computed(() => activeSources.value.size === ALL_SOURCES.length)

function selectAll() {
  if (isAllSelected.value) return
  activeSources.value = new Set(ALL_SOURCES)
}

function toggleSource(source: Source) {
  if (isAllSelected.value) {
    activeSources.value = new Set([source])
  } else if (activeSources.value.has(source)) {
    activeSources.value.delete(source)
    if (activeSources.value.size === 0) {
      activeSources.value = new Set(ALL_SOURCES)
    }
  } else {
    activeSources.value.add(source)
  }
  activeSources.value = new Set(activeSources.value)
}

function isSourceActive(source: Source): boolean {
  return !isAllSelected.value && activeSources.value.has(source)
}

const visibleEntries = computed(() =>
  isAllSelected.value
    ? entries.value
    : entries.value.filter(e => activeSources.value.has(e.source))
)

const canWrite = computed(() => !props.readonly && can(PERMISSIONS.clinicalNotes.write))

const itemByTreatmentId = computed(() => {
  const map = new Map<string, PlannedTreatmentItem>()
  for (const it of props.items) map.set(it.treatment_id, it)
  return map
})

const itemByPlanItemId = computed(() => {
  const map = new Map<string, PlannedTreatmentItem>()
  for (const it of props.items) map.set(it.id, it)
  return map
})

async function refresh() {
  loading.value = true
  try {
    entries.value = await listMergedForPlan(props.planId)
  } finally {
    loading.value = false
  }
}

defineExpose({ refresh })

function startNew() {
  editingId.value = null
  composerBody.value = ''
  composerOpen.value = true
}

function startEdit(entry: ClinicalNoteEntry) {
  if (!entry.note_id || entry.source !== 'plan') return
  editingId.value = entry.note_id
  composerBody.value = entry.body
  composerOpen.value = true
}

async function handleSubmit(payload: {
  body: string
  toothNumber: number | null
  attachmentDocumentIds: string[]
}) {
  saving.value = true
  try {
    if (editingId.value) {
      await updateNote(editingId.value, payload.body)
    } else {
      await createNote({
        note_type: 'treatment_plan',
        owner_type: 'plan',
        owner_id: props.planId,
        body: payload.body,
        attachment_document_ids: payload.attachmentDocumentIds
      })
    }
    composerOpen.value = false
    editingId.value = null
    composerBody.value = ''
    await refresh()
    emit('updated')
  } finally {
    saving.value = false
  }
}

async function handleDelete(entry: ClinicalNoteEntry) {
  if (!entry.note_id) return
  const ok = await deleteNote(entry.note_id)
  if (ok) {
    await refresh()
    emit('updated')
  }
}

function isOwnPlanNote(entry: ClinicalNoteEntry): boolean {
  return (
    canWrite.value
    && entry.source === 'plan'
    && !!entry.note_id
    && !!entry.author_id
    && entry.author_id === user.value?.id
  )
}

// Map merged-entry sources to NoteType so we can reuse useNoteTypeMeta()
// (color + icon) — gives the timeline visual parity with NoteCard /
// RecentNotesFeed: plan = secondary, treatment = success, visit = primary.
function sourceNoteType(source: Source): NoteType {
  if (source === 'plan') return 'treatment_plan'
  return 'treatment'
}

function sourceMeta(source: Source) {
  if (source === 'visit') {
    return {
      color: 'primary' as const,
      icon: 'i-lucide-calendar-check',
      borderColor: 'var(--color-primary-accent, #3b82f6)'
    }
  }
  const meta = metaFor(sourceNoteType(source))
  const borderMap: Record<Source, string> = {
    plan: 'var(--color-secondary-accent, #a855f7)',
    treatment: 'var(--color-success-accent, #22c55e)',
    visit: 'var(--color-primary-accent, #3b82f6)'
  }
  return {
    color: meta.color,
    icon: meta.icon,
    borderColor: borderMap[source]
  }
}

function sourceTypeLabel(source: Source): string {
  if (source === 'visit') return t('clinicalNotes.timeline.source.visit')
  if (source === 'treatment') return t('clinicalNotes.timeline.source.treatment')
  return t('clinicalNotes.timeline.source.plan')
}

function entryItemId(entry: ClinicalNoteEntry): string | null {
  if (entry.source === 'plan') return null
  if (entry.source === 'treatment') {
    return itemByTreatmentId.value.get(entry.owner_id)?.id ?? null
  }
  if (entry.source === 'visit' && entry.plan_item_id) {
    return itemByPlanItemId.value.get(entry.plan_item_id)?.id ?? null
  }
  return null
}

function handleEntryEnter(entry: ClinicalNoteEntry) {
  const itemId = entryItemId(entry)
  if (!itemId) return
  emit('item-hover', itemId)
}

function handleEntryLeave() {
  emit('item-hover', null)
}

function entryTreatmentName(entry: ClinicalNoteEntry): string | null {
  if (entry.source === 'plan') return null
  const item =
    entry.source === 'treatment'
      ? itemByTreatmentId.value.get(entry.owner_id)
      : entry.plan_item_id
        ? itemByPlanItemId.value.get(entry.plan_item_id)
        : undefined
  return item ? resolveTreatmentName(item) : null
}

function resolveTreatmentName(item: PlannedTreatmentItem): string | null {
  const names = item.catalog_item?.names || item.treatment?.catalog_item?.names
  if (names) {
    const localized = names[locale.value] || names.es
    if (localized) return localized
  }
  const clinicalType = item.treatment?.clinical_type
  if (clinicalType) {
    const key = `odontogram.treatments.types.${clinicalType}`
    const translated = t(key)
    if (translated !== key) return translated
    return clinicalType
  }
  return null
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString(locale.value)
  } catch {
    return iso
  }
}

function entryAuthorLabel(entry: ClinicalNoteEntry): string {
  const a = entry.author
  return a?.full_name || a?.email || t('clinicalNotes.author.unknown')
}

function entryAuthorInitials(entry: ClinicalNoteEntry): string {
  return entryAuthorLabel(entry)
    .split(/\s+/)
    .map(w => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join('')
    .toUpperCase()
}

watch(() => props.planId, refresh, { immediate: true })
</script>

<template>
  <div class="space-y-3">
    <header class="flex flex-wrap items-center gap-2 justify-between">
      <div
        class="flex flex-wrap items-center gap-1"
        role="group"
        :aria-label="t('clinicalNotes.feed.filterLabel')"
      >
        <UButton
          size="xs"
          :variant="isAllSelected ? 'solid' : 'soft'"
          color="neutral"
          icon="i-lucide-list"
          :aria-pressed="isAllSelected"
          @click="selectAll"
        >
          {{ t('clinicalNotes.feed.filterAll') }}
        </UButton>
        <span
          class="mx-1 h-4 w-px bg-default/60"
          aria-hidden="true"
        />
        <UButton
          v-for="source in ALL_SOURCES"
          :key="source"
          size="xs"
          :variant="isSourceActive(source) ? 'soft' : 'ghost'"
          :color="sourceMeta(source).color"
          :icon="sourceMeta(source).icon"
          :aria-pressed="isSourceActive(source)"
          @click="toggleSource(source)"
        >
          {{ sourceTypeLabel(source) }}
        </UButton>
      </div>
      <UButton
        v-if="canWrite && !composerOpen"
        icon="i-lucide-plus"
        size="sm"
        variant="soft"
        color="secondary"
        @click="startNew"
      >
        {{ t('clinicalNotes.timeline.addPlanNote') }}
      </UButton>
    </header>

    <NoteComposer
      v-if="composerOpen && canWrite"
      :note-type="'treatment_plan'"
      :initial-body="composerBody"
      :template-category="templateCategory"
      :patient-id="patientId"
      :busy="saving"
      autofocus
      @submit="handleSubmit"
      @cancel="composerOpen = false"
    />

    <div
      v-if="loading"
      class="text-center py-4 text-muted"
    >
      <UIcon
        name="i-lucide-loader-2"
        class="w-5 h-5 animate-spin mx-auto"
      />
    </div>

    <div
      v-else-if="entries.length === 0"
      class="text-center py-6 text-muted text-sm"
    >
      <UIcon
        name="i-lucide-notebook-pen"
        class="w-8 h-8 mx-auto mb-1 opacity-50"
      />
      {{ t('clinicalNotes.timeline.empty') }}
    </div>

    <div
      v-else-if="visibleEntries.length === 0"
      class="text-center py-6 text-muted text-sm"
    >
      {{ t('clinicalNotes.timeline.emptyForFilter') }}
    </div>

    <ul
      v-else
      class="space-y-2"
    >
      <li
        v-for="entry in visibleEntries"
        :key="entry.note_id || `${entry.source}-${entry.owner_id}-${entry.created_at}`"
        class="rounded-md p-3 bg-surface border border-default transition-colors hover:bg-elevated/40 focus-within:bg-elevated/40"
        :style="{ borderLeft: `3px solid ${sourceMeta(entry.source).borderColor}` }"
        @mouseenter="handleEntryEnter(entry)"
        @mouseleave="handleEntryLeave()"
        @focusin="handleEntryEnter(entry)"
        @focusout="handleEntryLeave()"
      >
        <header class="flex items-start justify-between gap-2 mb-2">
          <div class="flex items-start gap-2 min-w-0 flex-1">
            <UAvatar
              size="xs"
              :alt="entryAuthorLabel(entry)"
              class="shrink-0 mt-0.5"
            >
              <span class="text-caption font-semibold">{{ entryAuthorInitials(entry) }}</span>
            </UAvatar>
            <div class="flex flex-col min-w-0">
              <div class="flex flex-wrap items-center gap-1.5 min-w-0">
                <span class="font-medium text-sm truncate">
                  {{ entryAuthorLabel(entry) }}
                </span>
                <UBadge
                  :color="sourceMeta(entry.source).color"
                  variant="subtle"
                  size="xs"
                  class="shrink-0"
                >
                  <UIcon
                    :name="sourceMeta(entry.source).icon"
                    class="w-3 h-3 mr-1 shrink-0"
                  />
                  {{ sourceTypeLabel(entry.source) }}
                </UBadge>
                <span
                  v-if="entryTreatmentName(entry)"
                  class="text-caption text-default font-medium truncate max-w-[18rem]"
                >
                  · {{ entryTreatmentName(entry) }}
                </span>
              </div>
              <span class="text-caption text-muted truncate">
                {{ formatDate(entry.created_at) }}
              </span>
            </div>
          </div>
          <div
            v-if="isOwnPlanNote(entry)"
            class="flex gap-1 shrink-0"
          >
            <UButton
              icon="i-lucide-pencil"
              size="xs"
              variant="ghost"
              @click="startEdit(entry)"
            />
            <UButton
              icon="i-lucide-trash-2"
              size="xs"
              variant="ghost"
              color="error"
              @click="handleDelete(entry)"
            />
          </div>
        </header>
        <div class="text-sm whitespace-pre-wrap break-words">
          {{ entry.body }}
        </div>
      </li>
    </ul>
  </div>
</template>
