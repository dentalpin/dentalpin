import { mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TreatmentEditModal from '../../module_layers/odontogram/frontend/components/odontogram/TreatmentEditModal.vue'

// #1233: local state was only synced when the `treatment` prop changed.
// OdontogramChart keeps `editingTreatment` after Cancel, so opening the same
// treatment again showed the discarded status, notes and surfaces.

interface ModalVm {
  status: string
  notes: string
  selectedSurfaces: string[]
}

const treatment = {
  id: 'v1',
  treatment_id: 't1',
  tooth_number: 16,
  treatment_type: 'filling_composite',
  clinical_type: 'filling_composite',
  surfaces: ['O'],
  role: null,
  status: 'planned',
  recorded_at: '2026-01-01T00:00:00Z',
  notes: 'Original note',
  source_module: 'odontogram',
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  is_multi: false,
  teeth_count: 1
}

describe('TreatmentEditModal (#1233)', () => {
  it('reopening the same treatment after Cancel drops the discarded edits', async () => {
    const wrapper = await mountSuspended(TreatmentEditModal, { props: { open: true, treatment } })
    await flushPromises()
    const vm = wrapper.vm as unknown as ModalVm
    vm.status = 'existing'
    vm.notes = 'Edited but cancelled'
    vm.selectedSurfaces.push('M')

    // The chart closes the modal and keeps the same `treatment` value.
    await wrapper.setProps({ open: false })
    await flushPromises()
    await wrapper.setProps({ open: true })
    await flushPromises()

    expect(vm.status).toBe('planned')
    expect(vm.notes).toBe('Original note')
    expect(vm.selectedSurfaces).toEqual(['O'])
  })
})
