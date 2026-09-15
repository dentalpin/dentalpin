<script setup lang="ts">
const props = defineProps<{
  appointmentId: string
  open: boolean
}>()

const emit = defineEmits<{
  close: []
}>()

const { t } = useI18n()
const toast = useToast()
const { mintCheckinToken, fetchCheckinQr } = useAppointments()

const qrUrl = ref<string | null>(null)
const checkinUrl = ref('')
const isLoading = ref(false)
const loadFailed = ref(false)

watch(() => props.open, async (isOpen) => {
  if (!isOpen) {
    if (qrUrl.value) URL.revokeObjectURL(qrUrl.value)
    qrUrl.value = null
    checkinUrl.value = ''
    loadFailed.value = false
    return
  }
  isLoading.value = true
  try {
    const { token } = await mintCheckinToken(props.appointmentId)
    checkinUrl.value = `${window.location.origin}/check-in?t=${token}`
    qrUrl.value = await fetchCheckinQr(props.appointmentId)
  } catch {
    loadFailed.value = true
  } finally {
    isLoading.value = false
  }
}, { immediate: true })

async function copyLink() {
  await navigator.clipboard.writeText(checkinUrl.value)
  toast.add({ title: t('common.copied'), color: 'success' })
}
</script>

<template>
  <UModal
    :open="props.open"
    :title="t('appointments.checkin.qr')"
    @update:open="(v: boolean) => { if (!v) emit('close') }"
  >
    <template #body>
      <div class="flex flex-col items-center gap-3 p-4">
        <USkeleton
          v-if="isLoading"
          class="h-48 w-48"
        />
        <p v-else-if="loadFailed">
          {{ t('appointments.loadError') }}
        </p>
        <template v-else-if="qrUrl">
          <img
            :src="qrUrl"
            alt="QR"
            class="h-48 w-48"
          >
          <p class="text-sm text-muted text-center">
            {{ t('appointments.checkin.hint') }}
          </p>
          <div class="flex gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              icon="i-lucide-copy"
              @click="copyLink"
            >
              {{ t('appointments.checkin.copyLink') }}
            </UButton>
            <UButton
              color="neutral"
              variant="ghost"
              @click="emit('close')"
            >
              {{ t('common.close') }}
            </UButton>
          </div>
        </template>
      </div>
    </template>
  </UModal>
</template>
