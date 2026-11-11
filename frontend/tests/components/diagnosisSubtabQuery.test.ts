import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DiagnosisModeContainer from '../../module_layers/patients/frontend/components/patient/DiagnosisModeContainer.vue'

const replace = vi.fn()
mockNuxtImport('useRoute', () => () => ({ query: {} }))
mockNuxtImport('useRouter', () => () => ({ replace }))
const StubView = defineComponent(() => () => h('div', 'stub-view'))
mockNuxtImport('useModuleSlots', () => () => ({
  resolve: () => [{ id: 'periodontogram', component: StubView }]
}))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key }))

async function mountContainer() {
  return mountSuspended(DiagnosisModeContainer, {
    props: { patientId: 'p-1' },
    global: { stubs: { DiagnosisMode: true } }
  })
}

describe('DiagnosisModeContainer sub-tab URL sync (#573)', () => {
  beforeEach(() => replace.mockClear())

  it('writes clinicalMode alongside diagnosisView when a sub-tab is picked', async () => {
    const wrapper = await mountContainer()
    wrapper.findComponent({ name: 'UTabs' }).vm.$emit('update:modelValue', 'periodontogram')
    await flushPromises()
    expect(replace).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ clinicalMode: 'diagnosis', diagnosisView: 'periodontogram' })
      })
    )
  })

  it('clears diagnosisView when the odontogram default is picked again', async () => {
    const wrapper = await mountContainer()
    const tabs = wrapper.findComponent({ name: 'UTabs' })
    // activeKey starts at 'odontogram', so the watch only sees a return to
    // it after leaving it first.
    tabs.vm.$emit('update:modelValue', 'periodontogram')
    await flushPromises()
    replace.mockClear()
    tabs.vm.$emit('update:modelValue', 'odontogram')
    await flushPromises()
    expect(replace).toHaveBeenCalledWith(
      expect.objectContaining({
        query: expect.objectContaining({ clinicalMode: 'diagnosis', diagnosisView: undefined })
      })
    )
  })
})
