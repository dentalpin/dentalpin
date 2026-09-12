<script setup lang="ts">
import type { Document } from '~~/app/types'

interface Props {
  document: Document
  selected?: boolean
}

const props = defineProps<Props>()
defineEmits<{ open: [Document], select: [Document] }>()

const config = useRuntimeConfig()

const apiBaseUrl = computed(() =>
  import.meta.server ? config.apiBaseUrlServer : config.public.apiBaseUrl
)

// Build a fully-qualified, auth-aware thumb URL. The server returns a
// relative `/api/v1/...` path; we render it with an Authorization header
// via a fetched blob URL so <img> works without exposing credentials.
const thumbBlobUrl = ref<string | null>(null)

async function loadThumb() {
  const path = props.document.thumb_url ?? props.document.full_url
  if (!path) return
  try {
    const response = await $fetch<Blob>(path, {
      baseURL: apiBaseUrl.value,
      credentials: 'include',
      responseType: 'blob'
    })
    if (thumbBlobUrl.value) URL.revokeObjectURL(thumbBlobUrl.value)
    thumbBlobUrl.value = URL.createObjectURL(response)
  } catch {
    thumbBlobUrl.value = null
  }
}

watch(() => props.document.id, loadThumb, { immediate: true })
onBeforeUnmount(() => {
  if (thumbBlobUrl.value) URL.revokeObjectURL(thumbBlobUrl.value)
})

const captureLabel = computed(() => {
  const ts = props.document.captured_at ?? props.document.created_at
  return ts ? new Date(ts).toLocaleDateString() : ''
})

const subtypeLabel = computed(() => props.document.media_subtype ?? props.document.media_category ?? '')
</script>

<template>
  <button
    type="button"
    class="group relative aspect-square w-full overflow-hidden rounded-lg border border-default bg-elevated transition hover:ring-2 hover:ring-primary focus:outline-none focus:ring-2 focus:ring-primary"
    :class="{ 'ring-2 ring-primary': selected }"
    @click="$emit('open', document)"
  >
    <img
      v-if="thumbBlobUrl"
      :src="thumbBlobUrl"
      :alt="document.title"
      loading="lazy"
      class="h-full w-full object-cover"
    >
    <div
      v-else
      class="flex h-full w-full items-center justify-center text-muted"
    >
      <UIcon
        name="i-lucide-image"
        class="h-8 w-8"
      />
    </div>

    <!-- Subtype + date overlay -->
    <div
      class="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-1 bg-gradient-to-t from-black/70 to-transparent px-2 py-1.5 text-[11px] text-white opacity-0 transition group-hover:opacity-100"
    >
      <span class="truncate font-medium">{{ subtypeLabel }}</span>
      <span class="text-white/80">{{ captureLabel }}</span>
    </div>

    <!-- Pair badge -->
    <span
      v-if="document.paired_document_id"
      class="absolute top-1.5 end-1.5 rounded bg-primary/90 px-1.5 py-0.5 text-[10px] font-medium text-white"
    >
      <UIcon
        name="i-lucide-link"
        class="inline h-3 w-3"
      />
    </span>
  </button>
</template>
