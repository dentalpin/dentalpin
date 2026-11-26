import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import RequestsPage from '#module-layers/online_booking/frontend/pages/online-booking/index.vue'

const { get, post, put } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), put: vi.fn() }))
mockNuxtImport('useApi', () => () => ({ get, post, put }))
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
    put.mockReset()
    put.mockResolvedValue({ data: {} })
    get.mockImplementation(async (url: string) => {
      if (url === '/api/v1/online_booking/settings') return { data: { enabled: false, slot_minutes: 30, window_days: 30, min_notice_minutes: 60, public_url: null, professional_id: null, reasons: [{ id: 'first_visit', name_es: 'Primera visita', name_en: 'First visit', duration_minutes: 30, active: true }], accent_color: null, title_es: 'Cita', intro_es: null, title_en: null, intro_en: null } }
      if (url.includes('/patient-suggestions') || url.startsWith('/api/v1/patients')) return { data: [{ id: 'patient-1', first_name: 'Synthetic', last_name: 'Patient', email: 'synthetic@example.com' }] }
      if (url === '/api/v1/auth/professionals') return { data: [{ id: 'professional-1', first_name: 'Test', last_name: 'Dentist' }] }
      if (url === '/api/v1/agenda/cabinets') return { data: [{ id: 'cabinet-1', name: 'Room' }] }
      return { data: [row] }
    })
    post.mockResolvedValue({ data: {} })
  })
  afterEach(() => wrapper?.unmount())

  it('shows the primary action as enabled for a confirmed request', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Synthetic Person'))
    const button = wrapper.findAll('button').find(element => element.text() === 'onlineBooking.accept')
    expect(button).toBeDefined()
    expect(button!.attributes('disabled')).toBeUndefined()
    expect(button!.classes()).toContain('bg-primary')
  })

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

  it('suggests contact matches and splits a long name on its last space, editable', async () => {
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
    expect((fields[0]!.element as HTMLInputElement).value).toBe('María de la')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('Prueba')
    await fields[1]!.setValue('Otra')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('Otra')
  })

  async function openNewPatientForm(requestRow: Record<string, unknown>) {
    get.mockImplementation(async (url: string) => {
      if (url.includes('/patient-suggestions')) return { data: [] }
      if (url === '/api/v1/auth/professionals') return { data: [{ id: 'professional-1', first_name: 'Test', last_name: 'Dentist' }, { id: 'professional-2', first_name: 'Other', last_name: 'Dentist' }] }
      if (url === '/api/v1/agenda/cabinets') return { data: [] }
      return { data: [requestRow] }
    })
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain(String(requestRow.contact_name)))
    await clickByText(wrapper, 'onlineBooking.accept')
    await vi.waitFor(() => expect(get).toHaveBeenCalledWith('/api/v1/agenda/cabinets'))
    await wrapper.find('input[value="new"]').setValue()
    return wrapper.findAll('input[maxlength="100"]').map(field => (field.element as HTMLInputElement).value)
  }

  it('keeps a single-word contact name in the first name only', async () => {
    expect(await openNewPatientForm({ ...row, contact_name: 'Synthetic' })).toEqual(['Synthetic', ''])
  })

  it('prefers the separately captured first and last name over splitting', async () => {
    const values = await openNewPatientForm({ ...row, contact_name: 'Ana Maria Lopez Ruiz', contact_first_name: 'Ana Maria', contact_last_name: 'Lopez Ruiz' })
    expect(values).toEqual(['Ana Maria', 'Lopez Ruiz'])
  })

  it('preselects the professional configured on the request', async () => {
    await openNewPatientForm({ ...row, professional_id: 'professional-2' })
    await vi.waitFor(() => expect((wrapper!.vm as unknown as { professionalId: string }).professionalId).toBe('professional-2'))
    await clickByText(wrapper!, 'onlineBooking.confirmAccept')
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', expect.objectContaining({ professional_id: 'professional-2' }), { errorToast: false })
  })

  it('leaves the professional empty when the request professional is no longer listed', async () => {
    await openNewPatientForm({ ...row, professional_id: 'professional-gone' })
    expect((wrapper!.vm as unknown as { professionalId: string }).professionalId).toBe('')
    await clickByText(wrapper!, 'onlineBooking.confirmAccept')
    expect(post).not.toHaveBeenCalled()
  })

  it('shows booking limits, optional questions and the logo chooser', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await clickByText(wrapper, 'onlineBooking.settingsTitle')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('onlineBooking.rules'))
    expect(wrapper.text()).toContain('onlineBooking.perPatient')
    expect(wrapper.text()).toContain('onlineBooking.bufferBefore')
    expect(wrapper.text()).toContain('onlineBooking.askExisting')
    expect(wrapper.text()).toContain('onlineBooking.allowComment')
    expect(wrapper.find('input[type=color]').exists()).toBe(true)
    expect(wrapper.find('input[type=file]').exists()).toBe(true)
    const save = wrapper.findAll('button').find(button => button.text().includes('onlineBooking.saveSettings'))
    expect(save?.classes()).toContain('bg-primary')
  })

  it('labels the logo field differently from its upload button (#1226)', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await clickByText(wrapper, 'onlineBooking.settingsTitle')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('onlineBooking.rules'))
    const label = wrapper.findAll('label').find(element => element.text() === 'onlineBooking.logo')
    expect(label, 'missing logo field label').toBeDefined()
    const button = wrapper.findAll('button').find(element => element.text() === 'onlineBooking.logoUpload')
    expect(button, 'missing logo upload button').toBeDefined()
    expect(label!.text()).not.toBe(button!.text())
  })

  it('saves public branding without losing other settings', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await clickByText(wrapper, 'onlineBooking.settingsTitle')
    await vi.waitFor(() => expect(wrapper!.find('input[maxlength="120"]').exists()).toBe(true))
    await wrapper.find('input[maxlength="120"]').setValue('Reserva dental')
    await clickByText(wrapper, 'onlineBooking.saveSettings')
    await vi.waitFor(() => expect(put).toHaveBeenCalledWith('/api/v1/online_booking/settings', expect.objectContaining({ enabled: false, slot_minutes: 30, title_es: 'Reserva dental' })))
  })

  it('allows adding a visit reason and saving its duration', async () => {
    wrapper = await mountSuspended(RequestsPage)
    await clickByText(wrapper, 'onlineBooking.settingsTitle')
    await vi.waitFor(() => expect(wrapper!.text()).toContain('onlineBooking.visitReasons'))
    await clickByText(wrapper, 'onlineBooking.addReason')
    const names = wrapper.findAll('input[maxlength="80"]')
    await names[2]!.setValue('Tratamiento')
    await names[3]!.setValue('Treatment')
    const durations = wrapper.findAll('input[type="number"]')
    await durations[durations.length - 5]!.setValue('75')
    await clickByText(wrapper, 'onlineBooking.saveSettings')
    await vi.waitFor(() => expect(put).toHaveBeenCalledWith('/api/v1/online_booking/settings', expect.objectContaining({ reasons: expect.arrayContaining([expect.objectContaining({ name_es: 'Tratamiento', name_en: 'Treatment', duration_minutes: 75, active: true })]) })))
  })

  it('paginates the queue and announces successful rejection', async () => {
    get.mockResolvedValueOnce({ data: [row], total: 51, page: 1, page_size: 50 })
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

  it('requires a surname before creating a patient from a one-word name (#1044)', async () => {
    get.mockImplementation(async (url: string) => {
      if (url.includes('/patient-suggestions')) return { data: [] }
      if (url === '/api/v1/auth/professionals') return { data: [{ id: 'professional-1', first_name: 'Test', last_name: 'Dentist' }] }
      if (url === '/api/v1/agenda/cabinets') return { data: [] }
      return { data: [{ ...row, contact_name: 'Cher' }] }
    })
    wrapper = await mountSuspended(RequestsPage)
    await vi.waitFor(() => expect(wrapper!.text()).toContain('Cher'))
    await clickByText(wrapper, 'onlineBooking.accept')
    await wrapper.find('input[value="new"]').setValue()
    ;(wrapper.vm as unknown as { professionalId: string }).professionalId = 'professional-1'
    const fields = wrapper.findAll('input[maxlength="100"]')
    expect((fields[1]!.element as HTMLInputElement).value).toBe('')
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    expect(post).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('onlineBooking.nameRequired')
    await fields[1]!.setValue('Synthetic')
    await clickByText(wrapper, 'onlineBooking.confirmAccept')
    expect(post).toHaveBeenCalledWith('/api/v1/online_booking/requests/request-1/accept', expect.objectContaining({ first_name: 'Cher', last_name: 'Synthetic' }), { errorToast: false })
  })
})
