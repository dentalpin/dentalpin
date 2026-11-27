import { mountSuspended, mockNuxtImport } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DiagnosesCard from '#module-layers/odontogram/frontend/components/summary/DiagnosesCard.vue'

/**
 * #1162: the patient summary Diagnoses card read `tooth_number` and
 * `surfaces` off the treatment, but `TreatmentResponse` carries them on
 * each `teeth[]` member, so every row showed only the treatment name.
 */
const { get } = vi.hoisted(() => ({ get: vi.fn() }))

mockNuxtImport('useApi', () => () => ({ get }))

// useAsyncData caches by key (patient id), so each case uses its own.
let seq = 0
const patient = () => ({ id: `patient-${++seq}` })

function treatment(id: string, clinical_type: string, teeth: Array<[number, string[] | null]>) {
  return {
    id,
    clinical_type,
    scope: teeth.length > 1 ? 'multi_tooth' : teeth.length ? 'tooth' : 'global_mouth',
    status: 'planned',
    teeth: teeth.map(([tooth_number, surfaces], i) => ({
      id: `${id}-tooth-${i}`,
      tooth_record_id: `record-${tooth_number}`,
      tooth_number,
      role: null,
      surfaces
    }))
  }
}

async function mountWith(data: unknown[]) {
  get.mockResolvedValue({ data, total: data.length, page: 1, page_size: 50 })
  const card = await mountSuspended(DiagnosesCard, { props: { ctx: { patient: patient() } } })
  await vi.waitFor(() => expect(card.findAll('li')).toHaveLength(data.length))
  return card
}

describe('DiagnosesCard', () => {
  beforeEach(() => {
    get.mockReset()
  })

  it('shows the tooth number from teeth[]', async () => {
    const card = await mountWith([treatment('t1', 'crown', [[16, null]])])

    expect(card.find('li').text()).toContain('#16')
  })

  it('shows the surfaces of each tooth', async () => {
    const card = await mountWith([treatment('t1', 'filling_composite', [[26, ['O', 'M']]])])

    expect(card.find('li').text()).toMatch(/#26\s*\(O,M\)/)
  })

  it('lists every tooth of a multi-tooth treatment', async () => {
    const card = await mountWith([treatment('t1', 'bridge', [[14, null], [15, null], [16, null]])])

    expect(card.find('li').text()).toMatch(/#14\s+#15\s+#16/)
  })

  it('shows no tooth for a global treatment', async () => {
    const card = await mountWith([treatment('t1', 'other', [])])

    expect(card.find('li').text()).not.toContain('#')
  })
})
