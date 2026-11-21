<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-2xl font-bold">
          {{ t('documents.title') }}
        </h1>
        <p class="text-sm text-muted-foreground">
          {{ t('documents.subtitle') }}
        </p>
      </div>
      <UButton
        v-if="can(PERMISSIONS.generatedDocuments.write)"
        icon="i-lucide-plus"
        @click="openCreateModal"
      >
        {{ t('documents.newDocument') }}
      </UButton>
    </div>

    <!-- Filters -->
    <div class="flex items-center gap-4">
      <USelect
        v-model="filterType"
        :items="documentTypeOptions"
        :placeholder="t('documents.filterType')"
        class="w-48"
      />
      <USelect
        v-model="filterStatus"
        :items="statusOptions"
        :placeholder="t('documents.filterStatus')"
        class="w-40"
      />
    </div>

    <!-- Document list -->
    <div
      v-if="loading"
      class="space-y-4"
    >
      <USkeleton
        v-for="i in 5"
        :key="i"
        class="h-16 w-full"
      />
    </div>

    <div
      v-else-if="documents.length === 0"
      class="text-center py-12"
    >
      <p class="text-muted-foreground">
        {{ t('documents.empty') }}
      </p>
    </div>

    <div
      v-else
      class="space-y-2"
    >
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="flex items-center justify-between p-4 border rounded-lg hover:bg-muted/50"
      >
        <div class="flex items-center gap-4">
          <div class="flex-shrink-0">
            <UIcon
              :name="getDocTypeIcon(doc.document_type)"
              class="h-5 w-5 text-muted-foreground"
            />
          </div>
          <div>
            <p class="font-medium">
              {{ doc.title }}
            </p>
            <p class="text-sm text-muted-foreground">
              {{ getDocTypeLabel(doc.document_type) }} · {{ formatDate(doc.created_at) }}
            </p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <UBadge
            :color="getStatusColor(doc.status)"
            variant="soft"
          >
            {{ getStatusLabel(doc.status) }}
          </UBadge>
          <div
            v-if="can(PERMISSIONS.generatedDocuments.write)"
            class="flex items-center gap-1"
          >
            <UButton
              v-if="doc.status === 'draft' && doc.document_type !== 'informed_consent'"
              variant="ghost"
              size="sm"
              icon="i-lucide-pencil"
              @click="openEditModal(doc)"
            />
            <UButton
              v-if="doc.status === 'draft' && doc.document_type !== 'informed_consent'"
              variant="ghost"
              size="sm"
              icon="i-lucide-file-down"
              @click="generateDocument(doc)"
            />
            <UButton
              v-if="doc.status === 'generated'"
              variant="ghost"
              size="sm"
              icon="i-lucide-download"
              @click="downloadDocument(doc)"
            />
            <UButton
              v-if="doc.document_type !== 'informed_consent'"
              variant="ghost"
              size="sm"
              icon="i-lucide-archive"
              @click="archiveDocument(doc)"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div
      v-if="totalPages > 1"
      class="flex justify-center"
    >
      <UPagination
        v-model:page="currentPage"
        :items-per-page="pageSize"
        :total="total"
      />
    </div>

    <!-- Create/Edit Modal -->
    <DocumentCreateModal
      v-model:open="showCreateModal"
      :document="editingDocument"
      @created="onDocumentCreated"
      @updated="onDocumentUpdated"
    />
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { errorMessage } from '~~/app/utils/error'
import { parseDateOnly } from '~~/app/utils/wallClock'

const { t, locale } = useI18n()
const { can } = usePermissions()
const toast = useToast()
const { listDocuments, deleteDocument, generateDocument: generateDocumentRequest, downloadDocument: downloadDocumentRequest } = useManagedDocuments()

// State
const documents = ref<ManagedDocument[]>([])
const loading = ref(true)
const filterType = ref<GeneratedDocumentType | 'all'>('all')
const filterStatus = ref<'draft' | 'generated' | 'archived' | 'all'>('all')
const currentPage = ref(1)
const pageSize = 20
const total = ref(0)
const showCreateModal = ref(false)
const editingDocument = ref<ManagedDocument | null>(null)

const totalPages = computed(() => Math.ceil(total.value / pageSize))

// Options — the SelectItems use an explicit ``all`` sentinel (never the
// empty string) so a "reset" selection is a distinct, well-defined value
// that is simply dropped from the API query.
const documentTypeOptions = computed(() => [
  { label: t('documents.types.all'), value: 'all' },
  { label: t('documents.types.prescription'), value: 'prescription' },
  { label: t('documents.types.medical_certificate'), value: 'medical_certificate' },
  { label: t('documents.types.referral'), value: 'referral' },
  { label: t('documents.types.radiology_request'), value: 'radiology_request' },
  { label: t('documents.types.informed_consent'), value: 'informed_consent' }
])

const statusOptions = computed(() => [
  { label: t('documents.status.all'), value: 'all' },
  { label: t('documents.status.draft'), value: 'draft' },
  { label: t('documents.status.generated'), value: 'generated' },
  { label: t('documents.status.archived'), value: 'archived' }
])

// Methods
async function fetchDocuments() {
  loading.value = true
  try {
    const response = await listDocuments({
      page: currentPage.value,
      page_size: pageSize,
      document_type: filterType.value === 'all' ? undefined : filterType.value,
      status: filterStatus.value === 'all' ? undefined : filterStatus.value
    })
    documents.value = response.data
    total.value = response.total
  } finally {
    loading.value = false
  }
}

function getDocTypeIcon(type: string) {
  const icons: Record<string, string> = {
    prescription: 'i-lucide-pill',
    medical_certificate: 'i-lucide-clipboard-check',
    referral: 'i-lucide-send',
    radiology_request: 'i-lucide-scan'
  }
  return icons[type] || 'i-lucide-file'
}

function getDocTypeLabel(type: string) {
  return t(`documents.types.${type}`)
}

function getStatusColor(status: string): 'neutral' | 'success' | 'warning' {
  const colors: Record<string, 'neutral' | 'success' | 'warning'> = {
    draft: 'neutral',
    generated: 'success',
    archived: 'warning'
  }
  return colors[status] || 'neutral'
}

function getStatusLabel(status: string) {
  return t(`documents.status.${status}`)
}

function formatDate(date: string) {
  return parseDateOnly(date).toLocaleDateString()
}

function openCreateModal() {
  editingDocument.value = null
  showCreateModal.value = true
}

function openEditModal(doc: ManagedDocument) {
  editingDocument.value = doc
  showCreateModal.value = true
}

async function generateDocument(doc: ManagedDocument) {
  try {
    await generateDocumentRequest(doc.id, locale.value)
    toast.add({ title: t('documents.messages.generated'), color: 'success' })
    await fetchDocuments()
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  }
}

async function downloadDocument(doc: ManagedDocument) {
  try {
    await downloadDocumentRequest(doc.id)
    toast.add({ title: t('documents.messages.downloaded'), color: 'success' })
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('documents.messages.downloadFailed')), color: 'error' })
  }
}

async function archiveDocument(doc: ManagedDocument) {
  try {
    await deleteDocument(doc.id)
    toast.add({ title: t('documents.messages.archived'), color: 'success' })
    await fetchDocuments()
  } catch (error: unknown) {
    toast.add({ title: errorMessage(error, t('common.error')), color: 'error' })
  }
}

function onDocumentCreated() {
  showCreateModal.value = false
  fetchDocuments()
}

function onDocumentUpdated() {
  showCreateModal.value = false
  editingDocument.value = null
  fetchDocuments()
}

// Watchers
watch([filterType, filterStatus, currentPage], () => {
  fetchDocuments()
})

// Initial load
onMounted(() => {
  fetchDocuments()
})
</script>
