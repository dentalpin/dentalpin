// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SignatureCanvas from '../../app/components/shared/SignatureCanvas.vue'

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

async function setupCanvas(pixelRatio = 1, modelValue: string | null = null) {
  vi.stubGlobal('devicePixelRatio', pixelRatio)
  const ctx = {
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    clearRect: vi.fn(),
    lineWidth: 0
  }
  const png = 'data:image/png;base64,synthetic'
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D
  )
  const serialize = vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(png)
  const onUpdate = vi.fn()
  const wrapper = mount(SignatureCanvas, {
    props: { 'modelValue': modelValue, 'onUpdate:modelValue': onUpdate }
  })
  await nextTick()
  const canvas = wrapper.get('canvas')
  const capture = vi.fn()
  const release = vi.fn()
  Object.assign(canvas.element, {
    setPointerCapture: capture,
    hasPointerCapture: vi.fn(() => true),
    releasePointerCapture: release
  })
  vi.spyOn(canvas.element, 'getBoundingClientRect').mockReturnValue(
    new DOMRect(20, 30, 300, 90)
  )
  async function pointer(event: string, pointerId = 1, clientX = 30, clientY = 40) {
    await canvas.trigger(event, { pointerId, clientX, clientY, button: 0 })
  }
  return { wrapper, canvas, ctx, png, serialize, onUpdate, capture, release, pointer }
}

describe('SignatureCanvas', () => {
  it('sizes the displayed canvas to the PNG aspect ratio instead of a fixed height', async () => {
    const { wrapper, canvas } = await setupCanvas(3)
    try {
      const bitmapRatio = canvas.element.width / canvas.element.height
      const aspectClass = canvas.classes().find(name => name.startsWith('aspect-'))
      expect(bitmapRatio).toBe(10 / 3)
      expect(aspectClass).toBe('aspect-[10/3]')
      expect(canvas.classes().filter(name => name.startsWith('h-'))).toEqual(['h-auto'])
      expect(canvas.classes()).toContain('w-full')
    } finally {
      wrapper.unmount()
    }
  })

  it.each([1, 2])('scales strokes at devicePixelRatio %s and exports a PNG', async (ratio) => {
    const { wrapper, canvas, ctx, png, serialize, onUpdate, capture, pointer }
      = await setupCanvas(ratio)
    try {
      expect(canvas.element.width).toBe(600 * ratio)
      expect(canvas.element.height).toBe(180 * ratio)
      await pointer('pointerdown')
      expect(capture).toHaveBeenCalledWith(1)

      await pointer('pointermove', 2, 60, 65)
      expect(ctx.stroke).not.toHaveBeenCalled()

      await pointer('pointermove', 1, 60, 65)
      expect(ctx.moveTo).toHaveBeenCalledWith(20 * ratio, 20 * ratio)
      expect(ctx.lineTo).toHaveBeenCalledWith(80 * ratio, 70 * ratio)
      expect(ctx.lineWidth).toBe(2 * ratio)

      await pointer('pointerleave')
      await pointer('pointermove', 1, 340, 70)
      expect(ctx.lineTo).toHaveBeenLastCalledWith(640 * ratio, 80 * ratio)
      expect(serialize).not.toHaveBeenCalled()

      await pointer('pointerup')
      await pointer('lostpointercapture')
      expect(serialize).toHaveBeenCalledExactlyOnceWith('image/png')
      expect(onUpdate).toHaveBeenCalledExactlyOnceWith(png)
    } finally {
      wrapper.unmount()
    }
  })

  it.each([null, 'data:image/png;base64,previous'])('a stationary tap preserves %s', async (value) => {
    const { wrapper, ctx, serialize, onUpdate, pointer } = await setupCanvas(1, value)
    try {
      await pointer('pointerdown')
      await pointer('pointermove')
      await pointer('pointerup')
      expect(ctx.stroke).not.toHaveBeenCalled()
      expect(serialize).not.toHaveBeenCalled()
      expect(onUpdate).not.toHaveBeenCalled()
    } finally {
      wrapper.unmount()
    }
  })

  it('clears the full high DPI bitmap and cancels an active stroke', async () => {
    const { wrapper, ctx, release, serialize, onUpdate, pointer } = await setupCanvas(2, 'data:image/png;base64,previous')
    try {
      await pointer('pointerdown')
      await pointer('pointermove', 1, 60, 65)
      wrapper.vm.clear()
      expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 1200, 360)
      expect(release).toHaveBeenCalledWith(1)
      await pointer('lostpointercapture')
      await pointer('pointerup')
      expect(serialize).not.toHaveBeenCalled()
      expect(onUpdate).toHaveBeenCalledExactlyOnceWith(null)
    } finally {
      wrapper.unmount()
    }
  })
})
