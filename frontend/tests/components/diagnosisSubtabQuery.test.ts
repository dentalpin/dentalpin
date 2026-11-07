import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import DiagnosisModeContainer from '../../module_layers/patients/frontend/components/patient/DiagnosisModeContainer.vue'

const replace = vi.fn()
mockNuxtImport('useRoute', () => () => ({ query: {} }))
mockNuxtImport('useRouter', () => () => ({ replace }))
const StubView = defineComponent(() => () => h('div', 'stub-view'))
mockNuxtImport('useModuleSlots', () => () => ({
  resolve: () => [{ id: 'periodontogram', component: StubView }]
}))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

describe('DiagnosisModeContainer sub-tab URL sync (#573)', () => {
  it('writes clinicalMode alongside diagnosisView when a sub-tab is picked', async () => {
    const wrapper = await mountSuspended(DiagnosisModeContainer, {
      props: { patientId: 'p-1' },
      global: { stubs: { DiagnosisMode: true } }
    })
    const tabs = wrapper.findComponent({ name: 'UTabs' })
    expect(tabs.exists()).toBe(true)
    tabs.vm.$emit('update:modelValue', 'periodontogram')
    await flushPromises()
    expect(replace).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ clinicalMode: 'diagnosis', diagnosisView: 'periodontogram' })
      })
    )
  })
})
