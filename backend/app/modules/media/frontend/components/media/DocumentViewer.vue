<script setup lang="ts">
import type { Document } from '~~/app/types'

interface Props {
  document: Document | null
}

const props = defineProps<Props>()

const open = defineModel<boolean>('open', { default: false })

const { t } = useI18n()
const { getDocumentBlobUrl, downloadDocument } = useDocuments()

const blobUrl = ref<string | null>(null)
const loading = ref(false)
const error = ref(false)

const isPdf = computed(() => props.document?.mime_type === 'application/pdf')
const isImage = computed(() => props.document?.mime_type.startsWith('image/'))
const canView = computed(() => isPdf.value || isImage.value)

async function loadDocument() {
  if (!props.document) return

  loading.value = true
  error.value = false

  const url = await getDocumentBlobUrl(props.document.id)

  if (url) {
    blobUrl.value = url
  } else {
    error.value = true
  }

  loading.value = false
}

function cleanup() {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = null
  }
  error.value = false
}

function handleClose() {
  open.value = false
}

function handleDownload() {
  if (props.document) {
    downloadDocument(props.document.id, props.document.original_filename)
  }
}

watch(open, (isOpen) => {
  if (isOpen && props.document && canView.value) {
    loadDocument()
  } else if (!isOpen) {
    cleanup()
  }
})

onUnmounted(() => {
  cleanup()
})
</script>

<template>
  <UModal
    v-model:open="open"
    :ui="{ content: 'sm:max-w-6xl' }"
  >
    <template #content>
      <UCard
        :ui="{
          root: 'w-full',
          body: 'p-0',
          header: 'py-3 px-4'
        }"
      >
        <template #header>
          <div class="flex items-center justify-between">
            <div class="min-w-0 flex-1">
              <h3 class="font-semibold truncate">
                {{ document?.title }}
              </h3>
              <p class="text-caption text-subtle truncate">
                {{ document?.original_filename }}
              </p>
            </div>
            <div class="flex items-center gap-2 ml-4">
              <UButton
                icon="i-lucide-download"
                :aria-label="t('common.download')"
                variant="ghost"
                size="sm"
                :title="t('common.download')"
                @click="handleDownload"
              />
              <UButton
                icon="i-lucide-x"
                :aria-label="t('common.close')"
                variant="ghost"
                size="sm"
                :title="t('common.close')"
                @click="handleClose"
              />
            </div>
          </div>
        </template>

        <div class="h-[80vh]">
          <!-- Loading -->
          <div
            v-if="loading"
            class="h-full flex items-center justify-center"
          >
            <div class="text-center">
              <UIcon
                name="i-lucide-loader-2"
                class="w-8 h-8 animate-spin text-primary-accent"
              />
              <p class="mt-2 text-caption text-subtle">
                {{ t('documents.viewer.loading', 'Loading document...') }}
              </p>
            </div>
          </div>

          <!-- Error -->
          <div
            v-else-if="error"
            class="h-full flex items-center justify-center"
          >
            <div class="text-center">
              <UIcon
                name="i-lucide-file-x"
                class="w-12 h-12 text-subtle mx-auto"
              />
              <p class="mt-2 text-caption text-subtle">
                {{ t('documents.viewer.error', 'Could not load document') }}
              </p>
              <UButton
                variant="soft"
                size="sm"
                class="mt-3"
                @click="handleDownload"
              >
                {{ t('documents.viewer.downloadInstead', 'Download instead') }}
              </UButton>
            </div>
          </div>

          <!-- PDF Viewer -->
          <PDFViewer
            v-else-if="blobUrl && isPdf"
            :blob-url="blobUrl"
          />

          <!-- Image Viewer -->
          <ImageViewer
            v-else-if="blobUrl && isImage"
            :blob-url="blobUrl"
          />

          <!-- Unsupported type -->
          <div
            v-else-if="document && !canView"
            class="h-full flex items-center justify-center"
          >
            <div class="text-center">
              <UIcon
                name="i-lucide-file"
                class="w-12 h-12 text-subtle mx-auto"
              />
              <p class="mt-2 text-caption text-subtle">
                {{ t('documents.viewer.unsupported', 'Preview not available for this file type') }}
              </p>
              <UButton
                variant="soft"
                size="sm"
                class="mt-3"
                @click="handleDownload"
              >
                {{ t('common.download') }}
              </UButton>
            </div>
          </div>
        </div>
      </UCard>
    </template>
  </UModal>
</template>
