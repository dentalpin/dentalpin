<script setup lang="ts">
import type { Document, MediaCategory } from '~~/app/types'
import { PERMISSIONS } from '~~/app/config/permissions'

interface Props {
  patientId: string
  /** When 'picker', clicking a card emits `select` instead of opening lightbox. */
  mode?: 'browse' | 'picker'
}

const props = withDefaults(defineProps<Props>(), { mode: 'browse' })
const emit = defineEmits<{ select: [Document] }>()

const { t } = useI18n()
const { can } = usePermissions()
const { photos, total, loading, fetchPhotos } = usePhotos()

const canWrite = computed(() => can(PERMISSIONS.documents.write))

const categories: Array<{ key: 'all' | MediaCategory, label: string }> = [
  { key: 'all', label: t('photoGallery.cat.all', 'All') },
  { key: 'intraoral', label: t('photoGallery.cat.intraoral', 'Intraoral') },
  { key: 'extraoral', label: t('photoGallery.cat.extraoral', 'Extraoral') },
  { key: 'xray', label: t('photoGallery.cat.xray', 'X-ray') },
  { key: 'clinical', label: t('photoGallery.cat.clinical', 'Before/After') },
  { key: 'other', label: t('photoGallery.cat.other', 'Other') }
]

const activeCategory = ref<'all' | MediaCategory>('all')
const activeSubtype = ref<string | null>(null)

const showUpload = ref(false)
const lightboxOpen = ref(false)
const lightboxStartId = ref<string | null>(null)

async function load() {
  await fetchPhotos(props.patientId, {
    media_category: activeCategory.value === 'all' ? undefined : activeCategory.value,
    media_subtype: activeSubtype.value ?? undefined,
    page_size: 60
  })
}

watch(() => props.patientId, load, { immediate: true })
watch([activeCategory, activeSubtype], load)

function handleOpen(doc: Document) {
  if (props.mode === 'picker') {
    emit('select', doc)
    return
  }
  lightboxStartId.value = doc.id
  lightboxOpen.value = true
}

function handleUploaded() {
  showUpload.value = false
  load()
}
</script>

<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex flex-wrap items-center justify-between gap-2">
      <h3 class="text-lg font-semibold">
        {{ t('photoGallery.title', 'Patient gallery') }}
      </h3>
      <UButton
        v-if="canWrite && mode === 'browse'"
        icon="i-lucide-image-plus"
        size="sm"
        @click="showUpload = true"
      >
        {{ t('photoGallery.add', 'Add photo') }}
      </UButton>
    </div>

    <!-- Category rail -->
    <div class="flex flex-wrap gap-1.5 border-b border-default pb-2">
      <UButton
        v-for="cat in categories"
        :key="cat.key"
        :variant="activeCategory === cat.key ? 'solid' : 'soft'"
        :color="activeCategory === cat.key ? 'primary' : 'neutral'"
        size="xs"
        @click="activeCategory = cat.key; activeSubtype = null"
      >
        {{ cat.label }}
      </UButton>
    </div>

    <!-- Loading skeleton -->
    <div
      v-if="loading"
      class="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6"
    >
      <USkeleton
        v-for="i in 12"
        :key="i"
        class="aspect-square w-full"
      />
    </div>

    <!-- Empty -->
    <div
      v-else-if="photos.length === 0"
      class="rounded-lg border border-dashed border-default py-10 text-center text-muted"
    >
      <UIcon
        name="i-lucide-images"
        class="mx-auto h-10 w-10"
      />
      <p class="mt-2 text-sm">
        {{ t('photoGallery.empty', 'No photos yet') }}
      </p>
      <UButton
        v-if="canWrite && mode === 'browse'"
        variant="soft"
        size="sm"
        class="mt-3"
        @click="showUpload = true"
      >
        {{ t('photoGallery.uploadFirst', 'Upload the first one') }}
      </UButton>
    </div>

    <!-- Grid -->
    <div
      v-else
      class="grid grid-cols-2 gap-2 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6"
    >
      <PhotoCard
        v-for="photo in photos"
        :key="photo.id"
        :document="photo"
        @open="handleOpen"
      />
    </div>

    <!-- Pagination hint -->
    <p
      v-if="total > photos.length"
      class="text-xs text-muted"
    >
      {{ t('photoGallery.showingOf', `Showing ${photos.length} of ${total}`) }}
    </p>

    <!-- Upload modal -->
    <UModal
      v-model:open="showUpload"
      :ui="{ content: 'sm:max-w-2xl' }"
    >
      <template #content>
        <div class="bg-default rounded-lg overflow-hidden">
          <header class="flex items-center gap-3 border-b border-default px-5 py-4">
            <div class="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <UIcon
                name="i-lucide-image-plus"
                class="h-5 w-5"
              />
            </div>
            <div class="flex-1">
              <h3 class="text-base font-semibold leading-tight">
                {{ t('photoGallery.upload', 'Subir foto') }}
              </h3>
              <p class="text-xs text-muted">
                {{ t('photoGallery.uploadHelp', 'Clasifica para que aparezca en la categoría correcta') }}
              </p>
            </div>
            <UButton
              variant="ghost"
              color="neutral"
              icon="i-lucide-x"
              :aria-label="t('common.close')"
              size="sm"
              @click="showUpload = false"
            />
          </header>
          <div class="px-5 py-4">
            <PhotoUpload
              :patient-id="patientId"
              @uploaded="handleUploaded"
            />
          </div>
        </div>
      </template>
    </UModal>

    <!-- Lightbox -->
    <PhotoLightbox
      v-model:open="lightboxOpen"
      :documents="photos"
      :start-id="lightboxStartId"
      enable-pairing
      @pair-changed="load"
    />
  </div>
</template>
