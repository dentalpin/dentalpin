<script setup lang="ts">
const signaturePng = defineModel<string | null>({ required: true })
const canvasRef = ref<HTMLCanvasElement | null>(null)
const width = 600
const height = 180
const pixelRatio = ref(1)

let pointerId: number | null = null
let lastPoint = { x: 0, y: 0 }
let hasStroke = false

onMounted(() => {
  pixelRatio.value = Math.max(1, window.devicePixelRatio || 1)
})

function canvasPoint(canvas: HTMLCanvasElement, ev: PointerEvent) {
  const rect = canvas.getBoundingClientRect()
  if (!rect.width || !rect.height) return null
  return {
    x: (ev.clientX - rect.left) * canvas.width / rect.width,
    y: (ev.clientY - rect.top) * canvas.height / rect.height
  }
}

function startDraw(ev: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas || pointerId !== null || ev.button !== 0) return
  const point = canvasPoint(canvas, ev)
  if (!point) return

  canvas.setPointerCapture(ev.pointerId)
  pointerId = ev.pointerId
  lastPoint = point
  hasStroke = false
}

function moveDraw(ev: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas || ev.pointerId !== pointerId) return
  const point = canvasPoint(canvas, ev)
  if (!point || (point.x === lastPoint.x && point.y === lastPoint.y)) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return

  ctx.strokeStyle = '#0f172a'
  ctx.lineWidth = 2 * pixelRatio.value
  ctx.lineCap = 'round'
  ctx.beginPath()
  ctx.moveTo(lastPoint.x, lastPoint.y)
  ctx.lineTo(point.x, point.y)
  ctx.stroke()
  lastPoint = point
  hasStroke = true
}

function endDraw(ev: PointerEvent) {
  const canvas = canvasRef.value
  if (!canvas || ev.pointerId !== pointerId) return
  pointerId = null
  if (hasStroke) signaturePng.value = canvas.toDataURL('image/png')
  hasStroke = false
}

function clearCanvas() {
  const canvas = canvasRef.value
  if (!canvas) return
  const activePointer = pointerId
  pointerId = null
  hasStroke = false
  if (activePointer !== null && canvas.hasPointerCapture(activePointer)) {
    canvas.releasePointerCapture(activePointer)
  }
  canvas.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height)
  signaturePng.value = null
}

defineExpose({ clear: clearCanvas })
</script>

<template>
  <div class="rounded-md border border-[var(--ui-border)] bg-white touch-none">
    <canvas
      ref="canvasRef"
      :width="Math.round(width * pixelRatio)"
      :height="Math.round(height * pixelRatio)"
      class="block aspect-[10/3] w-full h-auto cursor-crosshair"
      @pointerdown="startDraw"
      @pointermove="moveDraw"
      @pointerup="endDraw"
      @pointercancel="endDraw"
      @lostpointercapture="endDraw"
    />
  </div>
</template>
