<script setup lang="ts">
const signaturePng = defineModel<string | null>({ required: true })
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

defineExpose({ clear: clearCanvas })
</script>

<template>
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
</template>
