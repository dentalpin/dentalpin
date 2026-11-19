import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import RequestsPage from '#module-layers/online_booking/frontend/pages/online-booking/index.vue'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
mockNuxtImport('useApi', () => () => ({ get, post }))
mockNuxtImport('usePermissions', () => () => ({ can: () => true }))
mockNuxtImport('useClinic', () => () => ({ currentClinic: ref({ timezone: 'Europe/Madrid' }) }))
mockNuxtImport('useI18n', () => () => ({ t: (key: string) => key, locale: ref('en') }))

const row = {
  id: 'request-1', status: 'confirmed', start_time: '2030-01-07T09:00:00Z',
  end_time: '2030-01-07T09:30:00Z', default_duration_minutes: 45, contact_name: 'Synthetic Person',
  contact_email: 'synthetic@example.com', contact_phone: '+34 600 000 000', reason: 'checkup'
}

function clickByText(wrapper: VueWrapper, text: string) {
  const button = wrapper.findAll('button').find(element => element.text().includes(text))
  expect(button, `missing button ${text}`).toBeDefined()
  return button!.trigger('click')
}

describe('online booking reception', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => {
    get.mockReset()
    post.mockReset()
    get.mockImplementation(async (url: string) => {
      if (url.includes('/patient-suggestions') || url.startsWith('/api/v1/patients')) return { data: [{ id: 'patient-1', first_name: 'Synthetic', last_name: 'Patient', email: 'synthetic@example.com' }] }
      if (url === '/api/v1/auth/professionals') return { data: [{ id: 'professional-1', first_name: 'Test', last_name: 'Dentist' }] }
      if (url === '/api/v1/agenda/cabinets') return { data: [{ id: 'cabinet-1', name: 'Room' }] }
      return { data: [row] }
    })
    post.mockResolvedValue({ data: {} })
  })
  afterEach(() => wrapper?.unmount())

  it('requires a selected patient before accepting and reports conflicts', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    await clickByText(wrapper, 'onlineBooking.accept')
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    expect(post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('onlineBooking.selectPatient')
    await wrapper.find('#patient-search').setValue('Synthetic')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Patient'))
    await clickByText(wrapper, 'Synthetic Patient')
    ;(wrapper.vm as unknown as { professionalId: string }).professionalId = 'professional-1'
    post.mockRejectedValueOnce({ statusCode: 409 })
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('onlineBooking.conflict'))
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', { patient_id: 'patient-1', professional_id: 'professional-1', cabinet_id: null, duration_minutes: 45 }, { errorToast: false })
  })

  it('creates a new patient only after explicit entry and confirmation', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    await clickByText(wrapper, 'onlineBooking.accept')
    await wrapper.find('input[value="new"]').setValue()
    const fields = wrapper.findAll('input[maxlength="100"]')
    expect(fields).toHaveLength(2)
    expect((fields[0]!.element as HTMLInputElement).value).toBe('Synthetic')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('Person')
    expect((wrapper.find('input[type=email]').element as HTMLInputElement).value).toBe('synthetic@example.com')
    expect((wrapper.find('input[type=tel]').element as HTMLInputElement).value).toBe('+34 600 000 000')
    ;(wrapper.vm as unknown as { professionalId: string }).professionalId = 'professional-1'
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', { first_name: 'Synthetic', last_name: 'Person', email: 'synthetic@example.com', phone: '+34 600 000 000', professional_id: 'professional-1', cabinet_id: null, duration_minutes: 45 }, { errorToast: false })
  })

  it('suggests contact matches and leaves a complex name unsplit and editable', async () => {
    get.mockImplementation(async (url: string) => {
      if (url.includes('/patient-suggestions')) return { data: [{ id: 'match', first_name: 'Match', last_name: 'Patient', phone: '+34 600 000 000' }] }
      if (url === '/api/v1/auth/professionals') return { data: [{ id: 'professional-1', first_name: 'Test', last_name: 'Dentist' }] }
      if (url === '/api/v1/agenda/cabinets') return { data: [] }
      return { data: [{ ...row, contact_name: 'María de la Prueba' }] }
    })
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('María de la Prueba'))
    await clickByText(wrapper, 'onlineBooking.accept')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Match Patient'))
    await wrapper.find('input[value="new"]').setValue()
    const fields = wrapper.findAll('input[maxlength="100"]')
    expect((fields[0]!.element as HTMLInputElement).value).toBe('María de la Prueba')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('')
    await fields[1]!.setValue('Prueba')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('Prueba')
  })

  it('paginates the queue and announces successful rejection', async () => {
    get.mockResolvedValueOnce({ data: [row], has_more: true })
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    await clickByText(wrapper, 'onlineBooking.next')
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/v1/online_booking/requests', { errorToast: false, query: { page: 2 } }))
    await clickByText(wrapper, 'onlineBooking.reject')
    await wrapper.find('textarea').setValue('Please call us')
    await clickByText(wrapper, 'onlineBooking.confirmReject')
    await vi.waitFor(() => expect(wrapper!.find('[role="status"]').text()).toContain('onlineBooking.rejected'))
  })

  it('requires a rejection message before sending', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    await clickByText(wrapper, 'onlineBooking.reject')
    await clickByText(wrapper, 'onlineBooking.confirmReject')
    expect(post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('onlineBooking.messageRequired')
    await wrapper.find('textarea').setValue('Please call us')
    await clickByText(wrapper, 'onlineBooking.confirmReject')
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/reject', { message: 'Please call us' }, { errorToast: false })
  })
})
