<script setup lang="ts">
import { PERMISSIONS } from '~~/app/config/permissions'
import { useDocuments, type GeneratedDocument, type DocumentType } from '../../composables/useDocuments'

definePageMeta({ middleware: ['auth'] })

const { t } = useI18n()
const { can } = usePermissions()
const docsApi = useDocuments()

if (!can(PERMISSIONS.documents.read)) {
  await navigateTo('/')
}

const canWrite = computed(() => can(PERMISSIONS.documents.write))

const DOC_TYPES: DocumentType[] = ['prescription', 'certificate', 'referral', 'radiology_request']
const typeOptions = computed(() => [
  { value: undefined, label: t('documents.filter.all') },
  ...DOC_TYPES.map(v => ({ value: v, label: t(`documents.types.${v}`) }))
])

const documents = ref<GeneratedDocument[]>([])
const loading = ref(false)
const filterType = ref<DocumentType | undefined>(undefined)

async function load() {
  loading.value = true
  try {
    const res = await docsApi.list({ document_type: filterType.value })
    documents.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(filterType, load)

async function download(doc: GeneratedDocument) {
  await docsApi.downloadPdf(doc)
}

const columns = [
  { accessorKey: 'document_type', header: t('documents.table.type') },
  { accessorKey: 'title', header: t('documents.table.title') },
  { accessorKey: 'created_at', header: t('documents.table.created_at') },
  { accessorKey: 'actions', header: '' }
]
</script>

<template>
  <div class="p-4 space-y-4">
    <div class="flex items-center justify-between">
      <h1 class="text-h2 text-default">
        {{ t('documents.title') }}
      </h1>
      <div v-if="canWrite" class="flex flex-wrap gap-2">
        <UButton icon="i-lucide-pill" variant="outline" size="sm" to="/documents/new/prescription">
          {{ t('documents.new.prescription') }}
        </UButton>
        <UButton icon="i-lucide-file-check" variant="outline" size="sm" to="/documents/new/certificate">
          {{ t('documents.new.certificate') }}
        </UButton>
        <UButton icon="i-lucide-send" variant="outline" size="sm" to="/documents/new/referral">
          {{ t('documents.new.referral') }}
        </UButton>
        <UButton icon="i-lucide-scan" variant="outline" size="sm" to="/documents/new/radiology-request">
          {{ t('documents.new.radiology_request') }}
        </UButton>
      </div>
    </div>

    <USelect
      v-model="filterType"
      :items="typeOptions"
      :placeholder="t('documents.filter.all')"
      class="max-w-xs"
    />

    <UTable :data="documents" :columns="columns" :loading="loading">
      <template #document_type-cell="{ row }">
        {{ t(`documents.types.${row.original.document_type}`) }}
      </template>
      <template #created_at-cell="{ row }">
        {{ new Date(row.original.created_at).toLocaleDateString() }}
      </template>
      <template #actions-cell="{ row }">
        <UButton
          icon="i-lucide-download"
          variant="ghost"
          size="xs"
          @click="download(row.original)"
        >
          {{ t('documents.table.download') }}
        </UButton>
      </template>
    </UTable>
  </div>
</template>
