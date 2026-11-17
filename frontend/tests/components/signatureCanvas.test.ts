// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { afterEach, describe, expect, it, vi } from 'vitest'
import SignatureCanvas from '../../app/components/shared/SignatureCanvas.vue'

afterEach(() => vi.restoreAllMocks())

describe('SignatureCanvas', () => {
  it.each(['pointerup', 'pointerleave'])('exports a stroke on %s and can clear it', async (endEvent) => {
    const ctx = {
      beginPath: vi.fn(),
      moveTo: vi.fn(),
      lineTo: vi.fn(),
      stroke: vi.fn(),
      clearRect: vi.fn()
    }
    const png = 'data:image/png;base64,synthetic'
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
      ctx as unknown as CanvasRenderingContext2D
    )
    const serialize = vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(png)
    const onUpdate = vi.fn()
    const wrapper = mount(SignatureCanvas, {
      props: { 'modelValue': null, 'onUpdate:modelValue': onUpdate }
    })
    try {
      const canvas = wrapper.get('canvas')
      await canvas.trigger('pointermove', { clientX: 8, clientY: 9 })
      expect(ctx.stroke).not.toHaveBeenCalled()
      await canvas.trigger('pointerdown', { clientX: 10, clientY: 20 })
      await canvas.trigger('pointermove', { clientX: 30, clientY: 40 })
      expect(ctx.moveTo).toHaveBeenCalledWith(10, 20)
      expect(ctx.lineTo).toHaveBeenCalledWith(30, 40)
      expect(ctx.stroke).toHaveBeenCalledOnce()
      expect(serialize).not.toHaveBeenCalled()

      await canvas.trigger(endEvent)
      expect(serialize).toHaveBeenCalledWith('image/png')
      expect(onUpdate).toHaveBeenLastCalledWith(png)

      await wrapper.setProps({ modelValue: png })
      wrapper.vm.clear()
      expect(ctx.clearRect).toHaveBeenCalledWith(0, 0, 600, 180)
      expect(onUpdate).toHaveBeenLastCalledWith(null)
    } finally {
      wrapper.unmount()
    }
  })
})
