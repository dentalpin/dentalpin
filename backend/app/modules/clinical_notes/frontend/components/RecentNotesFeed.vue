<script setup lang="ts">
/**
 * RecentNotesFeed — content of the patient Summary tab.
 *
 * Shows the most recent clinical notes across every type, with type filter
 * chips and a quick "+ Nota administrativa" composer. Mounted via the
 * ``patient.summary.feed`` slot from the patients module — this component
 * receives ``ctx.patient`` from the slot host.
 */

import type { NoteType, RecentNoteEntry, ClinicalNoteLinked } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  ctx: { patient: { id: string } }
}>()

const router = useRouter()
const { t } = useI18n()
const { can } = usePermissions()
const { metaFor, allTypes } = useNoteTypeMeta()
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
const activeFilters = ref<Set<NoteType>>(new Set(allTypes()))

// The six note types collapse into five user-facing chips: patient-level
// and appointment-level administrative notes share one "Administrativa"
// chip — their labels are identical, so two chips read as a duplicate
// (#203). The owner split stays intact in activeFilters / the API call.
const FILTER_GROUPS: { key: string, types: NoteType[] }[] = [
  { key: 'administrative', types: ['administrative', 'appointment_administrative'] },
  { key: 'diagnosis', types: ['diagnosis'] },
  { key: 'treatment', types: ['treatment'] },
  { key: 'treatment_plan', types: ['treatment_plan'] },
  { key: 'appointment_clinical', types: ['appointment_clinical'] }
]

const composerOpen = ref(false)
const editingId = ref<string | null>(null)
const composerBody = ref('')
const saving = ref(false)

const canRead = computed(() => can(PERMISSIONS.clinicalNotes.read))
const canWrite = computed(() => can(PERMISSIONS.clinicalNotes.write))

const patientId = computed(() => props.ctx?.patient?.id)

async function refresh() {
  if (!patientId.value || !canRead.value) return
  loading.value = true
  try {
    const types = activeFilters.value.size === allTypes().length
      ? undefined
      : Array.from(activeFilters.value)
    const fetched = await listRecentForPatient(patientId.value, {
      types,
      limit: PAGE_SIZE
    })
    entries.value = fetched
    hasMore.value = fetched.length === PAGE_SIZE
  } finally {
    loading.value = false
  }
}

async function loadMore() {
  if (!patientId.value || !canRead.value) return
  if (entries.value.length === 0) return
  loadingMore.value = true
  try {
    const before = entries.value[entries.value.length - 1]?.created_at
    const types = activeFilters.value.size === allTypes().length
      ? undefined
      : Array.from(activeFilters.value)
    const fetched = await listRecentForPatient(patientId.value, {
      types,
      limit: PAGE_SIZE,
      before
    })
    entries.value.push(...fetched)
    hasMore.value = fetched.length === PAGE_SIZE
  } finally {
    loadingMore.value = false
  }
}

const isAllSelected = computed(
  () => activeFilters.value.size === allTypes().length
)

function selectAll() {
  if (isAllSelected.value) return
  activeFilters.value = new Set(allTypes())
  refresh()
}

function toggleFilter(group: { types: NoteType[] }) {
  // From "all", clicking a chip pivots to that single group — fastest path
  // for the most common intent ("show me only diagnosis notes").
  if (isAllSelected.value) {
    activeFilters.value = new Set(group.types)
  } else if (group.types.every(type => activeFilters.value.has(type))) {
    for (const type of group.types) activeFilters.value.delete(type)
    if (activeFilters.value.size === 0) {
      activeFilters.value = new Set(allTypes())
    }
  } else {
    for (const type of group.types) activeFilters.value.add(type)
  }
  activeFilters.value = new Set(activeFilters.value)
  refresh()
}

function isActive(group: { types: NoteType[] }): boolean {
  return !isAllSelected.value && group.types.every(type => activeFilters.value.has(type))
}

const activeGroupCount = computed(
  () => FILTER_GROUPS.filter(g => g.types.every(type => activeFilters.value.has(type))).length
)

function startNew() {
  editingId.value = null
  composerBody.value = ''
  composerOpen.value = true
}

function startEdit(entry: RecentNoteEntry) {
  editingId.value = entry.id
  composerBody.value = entry.body
  composerOpen.value = true
}

async function handleSubmit(
  payload: { body: string, toothNumber: number | null, attachmentDocumentIds: string[] }
) {
  if (!patientId.value) return
  saving.value = true
  try {
    // Quick action only creates administrative notes — diagnosis /
    // treatment / treatment_plan notes are written from their own
    // surfaces (diagnosis sidebar, treatment row, plan timeline).
    // The composable toasts on failure and returns null — keep the
    // composer open with the draft intact so the user can retry.
    const saved = editingId.value
      ? await updateNote(editingId.value, payload.body)
      : await createNote({
          note_type: 'administrative',
          owner_type: 'patient',
          owner_id: patientId.value,
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

async function handleDelete(entry: RecentNoteEntry) {
  const confirmed = window.confirm(t('clinicalNotes.confirms.delete'))
  if (!confirmed) return
  const ok = await deleteNote(entry.id)
  if (ok) await refresh()
}

function canEditEntry(entry: RecentNoteEntry): boolean {
  return canWrite.value && !!entry.author?.id && entry.author.id === user.value?.id
}

function openLinked(linked: ClinicalNoteLinked) {
  if (!linked.id) return
  if (linked.kind === 'plan') {
    router.push(`/treatment-plans/${linked.id}`)
    return
  }
  if (linked.kind === 'treatment' || linked.kind === 'patient') {
    router.push({
      path: `/patients/${patientId.value}`,
      query: { tab: 'clinical', clinicalMode: 'diagnosis', tooth: linked.tooth_number ?? undefined }
    })
  }
}

watch(patientId, refresh, { immediate: true })
</script>

<template>
  <section
    v-if="canRead"
    class="space-y-4"
  >
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
          v-for="group in FILTER_GROUPS"
          :key="group.key"
          size="xs"
          :variant="isActive(group) ? 'soft' : 'ghost'"
          :color="metaFor(group.types[0]!).color"
          :icon="metaFor(group.types[0]!).icon"
          :aria-pressed="isActive(group)"
          @click="toggleFilter(group)"
        >
          {{ t(metaFor(group.types[0]!).labelKey) }}
        </UButton>
        <UButton
          v-if="!isAllSelected"
          size="xs"
          variant="ghost"
          color="neutral"
          icon="i-lucide-x"
          :aria-label="t('clinicalNotes.feed.filterClear')"
          @click="selectAll"
        >
          {{ t('clinicalNotes.feed.filterClear') }}
        </UButton>
      </div>
      <UButton
        v-if="canWrite"
        icon="i-lucide-plus"
        size="sm"
        color="primary"
        variant="soft"
        @click="startNew"
      >
        {{ t('clinicalNotes.feed.addAdministrative') }}
      </UButton>
    </header>

    <!-- Filter status line — makes the "todas" vs "filtrado" state explicit. -->
    <p
      v-if="!loading && !isAllSelected"
      class="text-caption text-muted -mt-2 flex items-center gap-1"
    >
      <UIcon
        name="i-lucide-filter"
        class="w-3.5 h-3.5"
      />
      {{ t('clinicalNotes.feed.filterStatus', { n: activeGroupCount, total: FILTER_GROUPS.length }) }}
    </p>

    <div v-if="composerOpen">
      <NoteComposer
        :note-type="editingId
          ? (entries.find(e => e.id === editingId)?.note_type ?? 'administrative')
          : 'administrative'"
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
        v-for="i in 3"
        :key="i"
        class="h-24 w-full"
      />
    </div>

    <div
      v-else-if="entries.length === 0"
      class="text-center py-10 text-muted"
    >
      <UIcon
        name="i-lucide-notebook-pen"
        class="w-10 h-10 mx-auto mb-2 opacity-50"
      />
      <p class="font-medium">
        {{ t('clinicalNotes.feed.empty.title') }}
      </p>
      <p class="text-sm">
        {{ t('clinicalNotes.feed.empty.help') }}
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
          :author="entry.author"
          :linked="entry.linked"
          :attachments="entry.attachments"
          :can-edit="canEditEntry(entry)"
          @edit="startEdit(entry)"
          @delete="handleDelete(entry)"
          @open-linked="openLinked"
        />
      </li>
    </ul>

    <div
      v-if="hasMore && !loading"
      class="flex justify-center"
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
  </section>
</template>
