<script setup lang="ts">
/**
 * AcceptInClinicModal — reception captures the patient's verbal
 * acceptance with optional tablet signature (canvas → base64 PNG).
 */

const props = defineProps<{
  open: boolean
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:open': [value: boolean]
  'confirm': [payload: { signer_name: string, signature_data?: { png?: string } }]
  'cancel': []
}>()

const { t } = useI18n()

const signerName = ref('')
const signaturePng = ref<string | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)

let drawing = false
let lastX = 0
let lastY = 0

function getCtx(): CanvasRenderingContext2D | null {
  return canvasRef.value?.getContext('2d') ?? null
}

function startDraw(ev: PointerEvent) {
  if (!canvasRef.value) return
  drawing = true
  const rect = canvasRef.value.getBoundingClientRect()
  lastX = ev.clientX - rect.left
  lastY = ev.clientY - rect.top
}

function moveDraw(ev: PointerEvent) {
  if (!drawing || !canvasRef.value) return
  const ctx = getCtx()
  if (!ctx) return
  const rect = canvasRef.value.getBoundingClientRect()
  const x = ev.clientX - rect.left
  const y = ev.clientY - rect.top
  ctx.strokeStyle = '#0f172a'
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(lastX, lastY)
  ctx.lineTo(x, y)
  ctx.stroke()
  lastX = x
  lastY = y
}

function endDraw() {
  if (!drawing || !canvasRef.value) return
  drawing = false
  signaturePng.value = canvasRef.value.toDataURL('image/png')
}

function clearCanvas() {
  if (!canvasRef.value) return
  const ctx = getCtx()
  if (ctx) ctx.clearRect(0, 0, canvasRef.value.width, canvasRef.value.height)
  signaturePng.value = null
}

function submit() {
  if (!signerName.value.trim()) return
  const payload: { signer_name: string, signature_data?: { png?: string } } = {
    signer_name: signerName.value.trim()
  }
  if (signaturePng.value) {
    payload.signature_data = { png: signaturePng.value }
  }
  emit('confirm', payload)
}

function reset() {
  signerName.value = ''
  signaturePng.value = null
  nextTick(clearCanvas)
}

watch(
  () => props.open,
  (opened) => {
    if (!opened) reset()
  }
)
</script>

<template>
  <UModal
    :open="open"
    @update:open="(v) => emit('update:open', v)"
  >
    <template #content>
      <UCard>
        <template #header>
          <h2 class="text-lg font-semibold">
            {{ t('budget.modals.acceptInClinic.title') }}
          </h2>
        </template>

        <div class="space-y-4 text-sm">
          <p>{{ t('budget.modals.acceptInClinic.description') }}</p>
          <UFormField
            :label="t('budget.modals.acceptInClinic.signerLabel')"
            required
          >
            <UInput
              v-model="signerName"
              :placeholder="t('budget.modals.acceptInClinic.signerLabel')"
            />
          </UFormField>

          <div>
            <div class="text-xs text-[var(--ui-text-muted)] mb-2">
              {{ t('budget.modals.acceptInClinic.captureSignature') }}
            </div>
            <div class="rounded-md border border-[var(--ui-border)] bg-white touch-none">
              <canvas
                ref="canvasRef"
                width="600"
                height="180"
                class="block w-full h-44 cursor-crosshair"
                @pointerdown="startDraw"
                @pointermove="moveDraw"
                @pointerup="endDraw"
                @pointerleave="endDraw"
              />
            </div>
            <UButton
              color="neutral"
              variant="ghost"
              size="xs"
              class="mt-2"
              @click="clearCanvas"
            >
              {{ t('common.clear') }}
            </UButton>
          </div>
        </div>

        <template #footer>
          <div class="flex justify-end gap-2">
            <UButton
              color="neutral"
              variant="ghost"
              :disabled="loading"
              @click="emit('cancel')"
            >
              {{ t('common.cancel') }}
            </UButton>
            <UButton
              color="primary"
              :loading="loading"
              :disabled="!signerName.trim()"
              @click="submit"
            >
              {{ t('budget.modals.acceptInClinic.submit') }}
            </UButton>
          </div>
        </template>
      </UCard>
    </template>
  </UModal>
</template>
