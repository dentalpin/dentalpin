<script setup lang="ts">
import type { Document, DocumentType } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

interface Props {
  patientId: string
}

const props = defineProps<Props>()

const { t } = useI18n()
const { can } = usePermissions()
const {
  documents,
  loading,
  total,
  fetchDocuments,
  downloadDocument,
  deleteDocument,
  updateDocument
} = useDocuments()

const canWrite = computed(() => can(PERMISSIONS.documents.write))

// Filter state
const selectedType = ref<string>('all')
const page = ref(1)
const pageSize = 12

// Document type options for filter
const typeFilterOptions = computed(() => [
  { label: t('documents.filter.allTypes'), value: 'all' },
  { label: t('documents.types.consent'), value: 'consent' },
  { label: t('documents.types.id_scan'), value: 'id_scan' },
  { label: t('documents.types.insurance'), value: 'insurance' },
  { label: t('documents.types.report'), value: 'report' },
  { label: t('documents.types.referral'), value: 'referral' },
  { label: t('documents.types.other'), value: 'other' }
])

// Modals
const showUploadModal = ref(false)
const showEditModal = ref(false)
const showDeleteConfirm = ref(false)
const showViewer = ref(false)
const selectedDocument = ref<Document | null>(null)
const viewerDocument = ref<Document | null>(null)

// Edit form state
const editTitle = ref('')
const editDescription = ref('')
const editDocumentType = ref<DocumentType>('other')
const isSavingEdit = ref(false)

// Document type options for edit form
const editTypeOptions = computed(() => [
  { label: t('documents.types.consent'), value: 'consent' },
  { label: t('documents.types.id_scan'), value: 'id_scan' },
  { label: t('documents.types.insurance'), value: 'insurance' },
  { label: t('documents.types.report'), value: 'report' },
  { label: t('documents.types.referral'), value: 'referral' },
  { label: t('documents.types.other'), value: 'other' }
])

// Load documents — restrict to non-photo kinds; the photo gallery owns
// `media_kind=photo|xray`.
async function loadDocuments() {
  const typeFilter = selectedType.value === 'all' ? undefined : selectedType.value as DocumentType
  await fetchDocuments(
    props.patientId,
    typeFilter,
    page.value,
    pageSize,
    'document'
  )
}

// Watchers
watch([selectedType, page], () => {
  loadDocuments()
})

watch(() => props.patientId, () => {
  page.value = 1
  loadDocuments()
}, { immediate: true })

// Handlers
function handleView(doc: Document) {
  viewerDocument.value = doc
  showViewer.value = true
}

function handleDownload(doc: Document) {
  downloadDocument(doc.id, doc.original_filename)
}

function handleEdit(doc: Document) {
  selectedDocument.value = doc
  editTitle.value = doc.title
  editDescription.value = doc.description || ''
  editDocumentType.value = doc.document_type as DocumentType
  showEditModal.value = true
}

async function handleEditSave() {
  if (!selectedDocument.value || !editTitle.value.trim()) return

  isSavingEdit.value = true
  const updated = await updateDocument(selectedDocument.value.id, {
    title: editTitle.value.trim(),
    description: editDescription.value.trim() || undefined,
    document_type: editDocumentType.value
  })
  isSavingEdit.value = false

  if (updated) {
    showEditModal.value = false
    selectedDocument.value = null
  }
}

function handleDeleteRequest(doc: Document) {
  selectedDocument.value = doc
  showDeleteConfirm.value = true
}

async function confirmDelete() {
  if (selectedDocument.value) {
    await deleteDocument(selectedDocument.value.id)
    showDeleteConfirm.value = false
    selectedDocument.value = null
  }
}

function handleUploaded() {
  showUploadModal.value = false
  loadDocuments()
}

// Pagination
const totalPages = computed(() => Math.ceil(total.value / pageSize))
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between gap-4">
      <h3 class="font-semibold text-lg">
        {{ t('documents.title', 'Documents') }}
      </h3>

      <div class="flex items-center gap-2">
        <!-- Type filter -->
        <USelectMenu
          v-model="selectedType"
          :items="typeFilterOptions"
          value-key="value"
          size="sm"
          class="w-40"
        />

        <!-- Upload button -->
        <UButton
          v-if="canWrite"
          icon="i-lucide-plus"
          size="sm"
          @click="showUploadModal = true"
        >
          {{ t('documents.add', 'Add') }}
        </UButton>
      </div>
    </div>

    <!-- Loading state -->
    <div
      v-if="loading"
      class="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <USkeleton
        v-for="i in 4"
        :key="i"
        class="h-24"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="documents.length === 0"
      class="text-center py-8 text-subtle"
    >
      <UIcon
        name="i-lucide-file-x"
        class="w-12 h-12 mx-auto mb-3 text-subtle"
      />
      <p>{{ t('documents.empty', 'No documents yet') }}</p>
      <UButton
        v-if="canWrite"
        variant="soft"
        size="sm"
        class="mt-3"
        @click="showUploadModal = true"
      >
        {{ t('documents.uploadFirst', 'Upload first document') }}
      </UButton>
    </div>

    <!-- Document grid -->
    <div
      v-else
      class="grid grid-cols-1 md:grid-cols-2 gap-4"
    >
      <DocumentCard
        v-for="doc in documents"
        :key="doc.id"
        :document="doc"
        @view="handleView"
        @download="handleDownload"
        @edit="handleEdit"
        @delete="handleDeleteRequest"
      />
    </div>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1"
      class="flex justify-center"
    >
      <UPagination
        v-model="page"
        :total="total"
        :page-count="pageSize"
      />
    </div>

    <!-- Upload Modal -->
    <UModal
      v-model:open="showUploadModal"
      :ui="{ content: 'sm:max-w-2xl' }"
    >
      <template #content>
        <div class="bg-default rounded-lg overflow-hidden">
          <header class="flex items-center gap-3 border-b border-default px-5 py-4">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <UIcon
                name="i-lucide-file-up"
                class="h-5 w-5"
              />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold leading-tight">
                {{ t('documents.upload', 'Subir documento') }}
              </h3>
              <p class="text-xs text-muted">
                {{ t('documents.uploadHelp', 'Clasifica el archivo para que aparezca en su categoría.') }}
              </p>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              size="sm"
              @click="showUploadModal = false"
            />
          </header>
          <div class="px-5 py-4">
            <DocumentUpload
              :patient-id="patientId"
              @uploaded="handleUploaded"
            />
          </div>
        </div>
      </template>
    </UModal>

    <!-- Delete Confirmation -->
    <UModal v-model:open="showDeleteConfirm">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="font-semibold text-danger-accent">
              {{ t('documents.deleteConfirm.title', 'Delete Document') }}
            </h3>
          </template>
          <p class="text-sm text-muted">
            {{ t('documents.deleteConfirm.message', 'Are you sure you want to delete this document? This action cannot be undone.') }}
          </p>
          <p
            v-if="selectedDocument"
            class="mt-2 font-medium"
          >
            {{ selectedDocument.title }}
          </p>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showDeleteConfirm = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                color="error"
                @click="confirmDelete"
              >
                {{ t('common.delete') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- Edit Modal -->
    <UModal v-model:open="showEditModal">
      <template #content>
        <UCard>
          <template #header>
            <h3 class="font-semibold">
              {{ t('documents.edit', 'Edit Document') }}
            </h3>
          </template>
          <div class="space-y-4">
            <UFormField :label="t('documents.fields.type', 'Type')">
              <USelectMenu
                v-model="editDocumentType"
                :items="editTypeOptions"
                value-key="value"
              />
            </UFormField>

            <UFormField
              :label="t('documents.fields.title', 'Title')"
              required
            >
              <UInput
                v-model="editTitle"
                :placeholder="t('documents.fields.titlePlaceholder', 'Document title')"
              />
            </UFormField>

            <UFormField :label="t('documents.fields.description', 'Description')">
              <UTextarea
                v-model="editDescription"
                :placeholder="t('documents.fields.descriptionPlaceholder', 'Optional notes')"
                :rows="2"
              />
            </UFormField>
          </div>
          <template #footer>
            <div class="flex justify-end gap-2">
              <UButton
                variant="ghost"
                @click="showEditModal = false"
              >
                {{ t('common.cancel') }}
              </UButton>
              <UButton
                :disabled="!editTitle.trim()"
                :loading="isSavingEdit"
                @click="handleEditSave"
              >
                {{ t('common.save') }}
              </UButton>
            </div>
          </template>
        </UCard>
      </template>
    </UModal>

    <!-- Document Viewer -->
    <DocumentViewer
      v-model:open="showViewer"
      :document="viewerDocument"
    />
  </div>
</template>
