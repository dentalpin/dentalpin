import { mountSuspended } from '@nuxt/test-utils/runtime'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h } from 'vue'

const routeState = vi.hoisted(() => ({
  path: '/patients/abc-123',
  query: {} as Record<string, unknown>,
  matched: [{ path: '/patients/:id' }]
}))

vi.mock('vue-router', async importOriginal => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useRoute: () => routeState
}))

async function runInSetup<T>(fn: () => T): Promise<T> {
  let captured!: T
  await mountSuspended(defineComponent({
    setup() {
      captured = fn()
      return () => h('div')
    }
  }))
  return captured
}

const DOCS = 'https://docs.example'

async function helpUrlFor(query: Record<string, unknown>): Promise<string> {
  routeState.query = query
  const help = await runInSetup(() => {
    const config = useRuntimeConfig()
    config.public.docsUrl = DOCS
    return useHelp()
  })
  return help.helpUrl.value
}

describe('useHelp', () => {
  beforeEach(() => {
    routeState.path = '/patients/abc-123'
    routeState.matched = [{ path: '/patients/:id' }]
    routeState.query = {}
  })

  it('anchors into the parent fragment for a named diagnosis sub-view', async () => {
    const url = await helpUrlFor({ tab: 'clinical', clinicalMode: 'diagnosis', diagnosisView: 'periodontogram' })
    expect(url).toBe(`${DOCS}/en/help/patients_id.html#periodontogram`)
  })

  it('does not anchor without a diagnosis query', async () => {
    const url = await helpUrlFor({})
    expect(url).toBe(`${DOCS}/en/help/patients_id.html`)
  })

  it('does not anchor for the odontogram default diagnosis view', async () => {
    const url = await helpUrlFor({ tab: 'clinical', clinicalMode: 'diagnosis' })
    expect(url).toBe(`${DOCS}/en/help/patients_id.html`)
  })

  it('does not anchor when diagnosisView leaks outside diagnosis mode', async () => {
    const url = await helpUrlFor({ tab: 'clinical', clinicalMode: 'plans', diagnosisView: 'periodontogram' })
    expect(url).toBe(`${DOCS}/en/help/patients_id.html`)
  })
})
