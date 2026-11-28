import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { flushPromises } from '@vue/test-utils'
import { afterAll, afterEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, ref } from 'vue'
import PlanDetailView from '../../module_layers/treatment_plan/frontend/components/clinical/PlanDetailView.vue'
import ClinicalTab from '../../module_layers/patients/frontend/components/patient/ClinicalTab.vue'

// #1270: every action on the plan screen follows the permission of the
// route it calls (plans.write / confirm / close / reactivate), not one
// `readonly` flag the patient file derived from odontogram.write and the
// standalone page never set.

const granted = vi.hoisted(() => ({ value: new Set<string>() }))
mockNuxtImport('usePermissions', () => () => ({
  can: (p: string) => granted.value.has(p),
  canAny: (...ps: string[]) => ps.some(p => granted.value.has(p)),
  isAdmin: ref(false)
}))
mockNuxtImport('useApi', () => () => ({ get: vi.fn(async () => ({ data: [] })), post: vi.fn(), put: vi.fn(), patch: vi.fn(), del: vi.fn(), raw: vi.fn() }))
// Layer locales are not loaded in the test app: echo the key.
mockNuxtImport('useI18n', () => () => ({
  t: (key: string) => key,
  locale: ref('en'),
  locales: ref([]),
  setLocale: vi.fn()
}))
// CI's frontend-test registers no module layers, so the layer composables
// are not auto-imported there: provide them as globals.
vi.stubGlobal('useTreatmentPlans', () => ({
  completeItem: vi.fn(),
  completeSession: vi.fn(),
  cancelSession: vi.fn(),
  removeItem: vi.fn(),
  reorderItems: vi.fn(),
  changeItemDoctor: vi.fn(),
  fetchPlan: vi.fn(),
  loading: ref(false),
  confirmPlan: vi.fn(),
  reopenPlan: vi.fn(),
  closePlan: vi.fn(),
  reactivatePlan: vi.fn(),
  logContact: vi.fn()
}))
vi.stubGlobal('useClinicalNotes', () => ({ createNote: vi.fn() }))
afterAll(() => vi.unstubAllGlobals())
afterEach(() => {
  granted.value = new Set()
})

// Role grants as the manifests define them (treatment_plan, odontogram, agenda).
const ROLES: Record<string, string[]> = {
  dentist: [
    'treatment_plan.plans.read', 'treatment_plan.plans.write', 'treatment_plan.plans.confirm',
    'treatment_plan.plans.close', 'treatment_plan.plans.reactivate',
    'odontogram.read', 'odontogram.write', 'odontogram.treatments.read', 'odontogram.treatments.write',
    'agenda.appointments.write', 'budget.read'
  ],
  hygienist: ['treatment_plan.plans.read', 'odontogram.read', 'odontogram.write', 'agenda.appointments.write'],
  assistant: ['treatment_plan.plans.read', 'treatment_plan.plans.write', 'odontogram.read', 'agenda.appointments.write'],
  receptionist: [
    'treatment_plan.plans.read', 'treatment_plan.plans.write',
    'treatment_plan.plans.close', 'treatment_plan.plans.reactivate', 'agenda.appointments.write'
  ]
}

const Prop = (name: string, props: string[]) => defineComponent({
  name,
  props,
  setup: (_, { slots }) => () => h('div', { 'data-stub': name }, slots.default?.())
})

const stubs = {
  OdontogramChart: Prop('OdontogramChart', ['mode', 'patientId', 'planId', 'planTitle', 'highlightedTeethProp', 'highlightedGlobalIds']),
  PlanTreatmentList: Prop('PlanTreatmentList', ['items', 'highlightedItems', 'readonly', 'allowComplete', 'planStatus', 'planProfessionalId', 'doctorEditable']),
  PlanNotesTimeline: Prop('PlanNotesTimeline', ['planId', 'patientId', 'items', 'readonly']),
  UDropdownMenu: Prop('UDropdownMenu', ['items']),
  ConfirmPlanModal: true,
  ReopenPlanModal: true,
  ClosePlanModal: true,
  ReactivatePlanModal: true,
  ContactLogModal: true,
  UModal: true
}

function plan(status: string, items = 1) {
  return {
    id: 'plan-1',
    clinic_id: 'c',
    patient_id: 'p-1',
    plan_number: 'PLAN-2026-0001',
    title: null,
    status,
    budget_id: null,
    closed_at: null,
    closure_reason: null,
    assigned_professional_id: null,
    items: Array.from({ length: items }, (_, i) => ({ id: `item-${i}`, status: 'pending', sessions: [] }))
  }
}

async function mountAs(role: string, status: string, extra: Record<string, unknown> = {}) {
  granted.value = new Set(ROLES[role])
  const wrapper = await mountSuspended(PlanDetailView, {
    props: { plan: plan(status), patientId: 'p-1', standalone: true, ...extra } as never,
    global: { stubs }
  })
  await flushPromises()
  return wrapper
}

const labels = (w: Awaited<ReturnType<typeof mountAs>>) =>
  w.findAll('button').map(b => b.text())
const menuLabels = (w: Awaited<ReturnType<typeof mountAs>>) => {
  const menu = w.findComponent({ name: 'UDropdownMenu' })
  return menu.exists() ? (menu.props('items') as Array<{ label: string }>).map(i => i.label) : []
}
const listReadonly = (w: Awaited<ReturnType<typeof mountAs>>) =>
  w.findComponent({ name: 'PlanTreatmentList' }).props('readonly')

describe('PlanDetailView gates each action on its own permission (#1270)', () => {
  it('dentist gets every action on a draft plan', async () => {
    const w = await mountAs('dentist', 'draft')
    expect(labels(w)).toContain('treatmentPlans.actions.confirm')
    expect(menuLabels(w)).toContain('clinical.plans.cancelPlan')
    expect(listReadonly(w)).toBe(false)
    expect(w.findComponent({ name: 'OdontogramChart' }).props('mode')).toBe('planning')
  })

  it('hygienist (plans.read only) sees the plan read-only', async () => {
    const w = await mountAs('hygienist', 'draft')
    expect(labels(w)).not.toContain('treatmentPlans.actions.confirm')
    expect(menuLabels(w)).not.toContain('clinical.plans.cancelPlan')
    expect(listReadonly(w)).toBe(true)
    expect(w.findComponent({ name: 'PlanTreatmentList' }).props('doctorEditable')).toBe(false)
    expect(w.findComponent({ name: 'OdontogramChart' }).props('mode')).toBe('view-only')
  })

  it('assistant (plans.write) edits items but gets neither Confirm nor Cancel plan', async () => {
    const w = await mountAs('assistant', 'draft')
    expect(labels(w)).not.toContain('treatmentPlans.actions.confirm')
    expect(menuLabels(w)).not.toContain('clinical.plans.cancelPlan')
    expect(listReadonly(w)).toBe(false)
    // No odontogram.treatments.write: the chart cannot create treatments.
    expect(w.findComponent({ name: 'OdontogramChart' }).props('mode')).toBe('view-only')
  })

  it('receptionist edits, cancels and reactivates but cannot confirm', async () => {
    const draft = await mountAs('receptionist', 'draft')
    expect(labels(draft)).not.toContain('treatmentPlans.actions.confirm')
    expect(menuLabels(draft)).toContain('clinical.plans.cancelPlan')
    expect(listReadonly(draft)).toBe(false)

    const closed = await mountAs('receptionist', 'closed')
    expect(labels(closed)).toContain('treatmentPlans.actions.reactivate')
  })

  it('only roles with plans.reactivate see Reactivate', async () => {
    const w = await mountAs('assistant', 'closed')
    expect(labels(w)).not.toContain('treatmentPlans.actions.reactivate')
  })

  it('an explicit readonly still hides every action, even for the dentist', async () => {
    const w = await mountAs('dentist', 'draft', { readonly: true })
    expect(labels(w)).not.toContain('treatmentPlans.actions.confirm')
    expect(menuLabels(w)).toEqual([])
    expect(listReadonly(w)).toBe(true)
    expect(w.findComponent({ name: 'OdontogramChart' }).props('mode')).toBe('view-only')
  })
})

describe('patient file does not derive plan read-only from odontogram.write (#1270)', () => {
  it('ClinicalTab does not pass its odontogram readonly to the plans mode', async () => {
    granted.value = new Set(ROLES.assistant)
    const wrapper = await mountSuspended(ClinicalTab, {
      // The patient page passes readonly = !can(odontogram.write): true for the assistant.
      props: { patientId: 'p-1', readonly: true },
      global: {
        stubs: {
          ClinicalModeToggle: Prop('ClinicalModeToggle', ['modelValue']),
          HistoryMode: true,
          DiagnosisModeContainer: Prop('DiagnosisModeContainer', ['patientId', 'readonly']),
          PlansMode: Prop('PlansMode', ['patientId', 'initialPlanId', 'readonly']),
          AppointmentsMode: true,
          TreatmentPlanModal: true
        }
      }
    })
    await flushPromises()
    // Diagnosis keeps the odontogram gate.
    expect(wrapper.findComponent({ name: 'DiagnosisModeContainer' }).props('readonly')).toBe(true)
    wrapper.findComponent({ name: 'ClinicalModeToggle' }).vm.$emit('update:modelValue', 'plans')
    await flushPromises()
    expect(wrapper.findComponent({ name: 'PlansMode' }).props('readonly')).toBeFalsy()
  })
})
