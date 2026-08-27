<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold">{{ t('patientDetail.tabs.documents') }}</h3>
      <UButton
        v-if="can(PERMISSIONS.generatedDocuments.write)"
        size="sm"
        icon="i-lucide-plus"
        @click="openCreateModal"
      >
        {{ t('documents.newDocument') }}
      </UButton>
    </div>

    <div v-if="loading" class="space-y-2">
      <USkeleton v-for="i in 3" :key="i" class="h-12 w-full" />
    </div>

    <div v-else-if="documents.length === 0" class="text-center py-8">
      <p class="text-muted-foreground">{{ t('documents.emptyPatient') }}</p>
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="doc in documents"
        :key="doc.id"
        class="flex items-center justify-between p-3 border rounded-lg"
      >
        <div class="flex items-center gap-3">
          <UIcon
            :name="getDocTypeIcon(doc.document_type)"
            class="h-4 w-4 text-muted-foreground"
          />
          <div>
            <p class="text-sm font-medium">{{ doc.title }}</p>
            <p class="text-xs text-muted-foreground">
              {{ getDocTypeLabel(doc.document_type) }} · {{ formatDate(doc.created_at) }}
            </p>
          </div>
        </div>
        <UBadge :color="getStatusColor(doc.status)" variant="soft" size="sm">
          {{ getStatusLabel(doc.status) }}
        </UBadge>
      </div>
    </div>

    <DocumentCreateModal
      v-model:open="showCreateModal"
      :initial-patient-id="patientId"
      @created="onDocumentCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'

const props = defineProps<{
  patientId: string
}>()

const { t } = useI18n()
const { can } = usePermissions()
const { listDocuments } = useDocuments()

const documents = ref<any[]>([])
const loading = ref(true)
const showCreateModal = ref(false)

async function fetchDocuments() {
  loading.value = true
  try {
    const response = await listDocuments({ patient_id: props.patientId })
    documents.value = response.data
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

function getStatusColor(status: string) {
  const colors: Record<string, string> = {
    draft: 'neutral',
    generated: 'success',
    archived: 'warning'
  }
  return (colors[status] || 'neutral') as any
}

function getStatusLabel(status: string) {
  return t(`documents.status.${status}`)
}

function formatDate(date: string) {
  return new Date(date).toLocaleDateString()
}

function openCreateModal() {
  showCreateModal.value = true
}

function onDocumentCreated() {
  showCreateModal.value = false
  fetchDocuments()
}

onMounted(() => {
  fetchDocuments()
})
</script>
