<script setup lang="ts">
/**
 * Study viewer: backend-rendered PNG (server-side windowing) with the
 * study metadata below. The <img> fires @error natively, so the alert
 * below actually shows when a render fails — unlike the old iframe
 * fallback, which silently embedded the Nuxt 404 page.
 */
const props = defineProps<{ studyId: string }>()

const { t } = useI18n()
const { renderUrl } = useImagingViewer()

const failed = ref(false)
watch(() => props.studyId, () => {
  failed.value = false
})
</script>

<template>
  <div class="flex flex-col gap-2">
    <UAlert
      v-if="failed"
      color="warning"
      :title="t('imagingViewer.viewer.unavailable')"
      :description="t('imagingViewer.viewer.fallbackHint')"
    />
    <img
      v-if="!failed"
      :src="renderUrl(props.studyId)"
      class="w-full rounded-lg border"
      :alt="t('imagingViewer.viewer.title')"
      draggable="false"
      @error="failed = true"
    >
    <p class="text-xs text-gray-500">
      {{ t('imagingViewer.viewer.visualizationNote') }}
    </p>
  </div>
</template>
