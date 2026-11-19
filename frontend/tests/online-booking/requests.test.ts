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
  end_time: '2030-01-07T09:30:00Z', contact_name: 'Synthetic Person',
  contact_email: 'synthetic@example.com', contact_phone: null, reason: 'checkup'
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
    get.mockImplementation(async (url: string) => url.startsWith('/api/v1/patients')
      ? { data: [{ id: 'patient-1', first_name: 'Synthetic', last_name: 'Patient' }] }
      : { data: [row] })
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
    post.mockRejectedValueOnce({ statusCode: 409 })
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('onlineBooking.conflict'))
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', { patient_id: 'patient-1' }, { errorToast: false })
  })

  it('creates a new patient only after explicit entry and confirmation', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    await clickByText(wrapper, 'onlineBooking.accept')
    await wrapper.find('input[value="new"]').setValue()
    const fields = wrapper.findAll('input[maxlength="100"]')
    expect(fields).toHaveLength(2)
    await fields[0]!.setValue('Synthetic')
    await fields[1]!.setValue('Person')
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', { first_name: 'Synthetic', last_name: 'Person' }, { errorToast: false })
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
