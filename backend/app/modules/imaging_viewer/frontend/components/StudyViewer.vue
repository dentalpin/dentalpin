<script setup lang="ts">
/**
 * Embedded DICOM viewer (OHIF build served from this layer's public dir).
 * The iframe stays same-origin so the host session (JWT) rides along;
 * study bytes come only from our clinic-scoped frame proxy.
 */
const props = defineProps<{ studyId: string }>()

const { t } = useI18n()
const { frameUrl } = useImagingViewer()

const viewerSrc = computed(() => `/ohif/viewer?study=${props.studyId}`)
const fallbackSrc = computed(() => frameUrl(props.studyId))
const failed = ref(false)
</script>

<template>
  <div class="flex flex-col gap-2">
    <UAlert
      v-if="failed"
      color="warning"
      :title="t('imagingViewer.viewer.unavailable')"
      :description="t('imagingViewer.viewer.fallbackHint')"
    />
    <iframe
      v-if="!failed"
      :src="viewerSrc"
      class="h-[70vh] w-full rounded-lg border"
      :title="t('imagingViewer.viewer.title')"
      @error="failed = true"
    />
    <UButton
      icon="i-lucide-download"
      variant="soft"
      :to="fallbackSrc"
      target="_blank"
    >
      {{ t('imagingViewer.viewer.downloadOriginal') }}
    </UButton>
    <p class="text-xs text-gray-500">
      {{ t('imagingViewer.viewer.visualizationNote') }}
    </p>
  </div>
</template>
