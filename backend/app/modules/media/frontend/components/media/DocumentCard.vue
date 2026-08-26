<script setup lang="ts">
import type { Document } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

interface Props {
  document: Document
}

const props = defineProps<Props>()

const emit = defineEmits<{
  view: [document: Document]
  download: [document: Document]
  delete: [document: Document]
  edit: [document: Document]
}>()

const { t } = useI18n()
const { can } = usePermissions()
const { formatFileSize, getDocumentTypeLabel, getMimeTypeIcon, getDocumentBlobUrl } = useDocuments()

const canWrite = computed(() => can(PERMISSIONS.documents.write))

// Thumbnail for images
const isImage = computed(() => props.document.mime_type.startsWith('image/'))
const thumbnailUrl = ref<string | null>(null)
const thumbnailLoading = ref(false)

async function loadThumbnail() {
  if (!isImage.value || thumbnailUrl.value) return
  thumbnailLoading.value = true
  thumbnailUrl.value = await getDocumentBlobUrl(props.document.id)
  thumbnailLoading.value = false
}

onMounted(() => {
  if (isImage.value) {
    loadThumbnail()
  }
})

onUnmounted(() => {
  if (thumbnailUrl.value) {
    URL.revokeObjectURL(thumbnailUrl.value)
  }
})

const canView = computed(() => {
  const mime = props.document.mime_type
  return mime === 'application/pdf' || mime.startsWith('image/')
})

const formattedDate = computed(() => {
  const date = new Date(props.document.created_at)
  return date.toLocaleDateString()
})

const uploaderName = computed(() => {
  if (props.document.uploader) {
    return `${props.document.uploader.first_name} ${props.document.uploader.last_name}`
  }
  return ''
})

function handleView() {
  emit('view', props.document)
}

function handleDownload() {
  emit('download', props.document)
}

function handleDelete() {
  emit('delete', props.document)
}

function handleEdit() {
  emit('edit', props.document)
}
</script>

<template>
  <UCard class="group">
    <div class="flex items-start gap-4">
      <!-- Thumbnail / Icon -->
      <div class="flex-shrink-0">
        <div
          v-if="isImage && thumbnailUrl"
          class="w-12 h-12 rounded-lg overflow-hidden bg-surface-muted"
        >
          <img
            :src="thumbnailUrl"
            :alt="document.title"
            class="w-full h-full object-cover"
          >
        </div>
        <div
          v-else-if="isImage && thumbnailLoading"
          class="w-12 h-12 rounded-lg bg-surface-muted flex items-center justify-center"
        >
          <USkeleton class="w-full h-full" />
        </div>
        <div
          v-else
          class="w-12 h-12 rounded-lg bg-[var(--color-primary-soft)] flex items-center justify-center"
        >
          <UIcon
            :name="getMimeTypeIcon(document.mime_type)"
            class="w-6 h-6 text-primary-accent"
          />
        </div>
      </div>

      <!-- Content -->
      <div class="flex-grow min-w-0">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h4 class="font-medium text-sm truncate">
              {{ document.title }}
            </h4>
            <div class="flex items-center gap-2 mt-1">
              <UBadge
                color="neutral"
                variant="subtle"
                size="xs"
              >
                {{ getDocumentTypeLabel(document.document_type as any) }}
              </UBadge>
              <span class="text-caption text-subtle">{{ formatFileSize(document.file_size) }}</span>
            </div>
          </div>

          <!-- Actions -->
          <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <UButton
              v-if="canView"
              icon="i-lucide-eye"
              :aria-label="t('common.viewDetails')"
              color="neutral"
              variant="ghost"
              size="xs"
              :title="t('common.view')"
              @click="handleView"
            />
            <UButton
              icon="i-lucide-download"
              :aria-label="t('common.download')"
              color="neutral"
              variant="ghost"
              size="xs"
              :title="t('common.download')"
              @click="handleDownload"
            />
            <UButton
              v-if="canWrite"
              icon="i-lucide-pencil"
              :aria-label="t('common.edit')"
              color="neutral"
              variant="ghost"
              size="xs"
              :title="t('common.edit')"
              @click="handleEdit"
            />
            <UButton
              v-if="canWrite"
              icon="i-lucide-trash-2"
              :aria-label="t('common.delete')"
              color="error"
              variant="ghost"
              size="xs"
              :title="t('common.delete')"
              @click="handleDelete"
            />
          </div>
        </div>

        <!-- Description -->
        <p
          v-if="document.description"
          class="text-caption text-subtle mt-2 line-clamp-2"
        >
          {{ document.description }}
        </p>

        <!-- Meta -->
        <div class="flex items-center gap-2 mt-2 text-caption text-subtle">
          <span>{{ formattedDate }}</span>
          <span v-if="uploaderName">{{ uploaderName }}</span>
        </div>
      </div>
    </div>
  </UCard>
</template>
