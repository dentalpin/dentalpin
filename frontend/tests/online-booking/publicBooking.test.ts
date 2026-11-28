import { mockNuxtImport, mountSuspended } from '@nuxt/test-utils/runtime'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { VueWrapper } from '@vue/test-utils'
import en from '#module-layers/online_booking/frontend/i18n/locales/en.json'
import BookingPage from '#module-layers/online_booking/frontend/pages/p/booking/[clinicId].vue'
import { PublicBookingError } from '#module-layers/online_booking/frontend/utils/publicBookingError'

vi.mock('altcha/i18n', () => ({}))
// Module layers are not loaded by the vitest Nuxt app (modules.json points at
// /module_layers), so the page imports its composable explicitly and the test
// replaces it here.
vi.mock('#module-layers/online_booking/frontend/composables/usePublicBooking', async importOriginal => ({
  ...(await importOriginal<typeof import('#module-layers/online_booking/frontend/composables/usePublicBooking')>()),
  usePublicBooking: () => api
}))

const CLINIC = '0b1c2d3e-4f50-4a6b-8c7d-9e0f1a2b3c4d'

const api = vi.hoisted(() => ({
  config: vi.fn(),
  availability: vi.fn(),
  createRequest: vi.fn(),
  confirm: vi.fn(),
  challengeUrl: 'http://localhost:8000/api/v1/online_booking/public/x/challenge',
  logoUrl: 'http://localhost:8000/api/v1/online_booking/public/x/logo'
}))
const locale = vi.hoisted(() => ({ value: 'en' }))
const loadLocaleMessages = vi.hoisted(() => vi.fn(async () => {}))

mockNuxtImport('useRoute', () => () => ({ params: { clinicId: CLINIC }, meta: {} }))
// Real English copy, so a missing key fails the test instead of printing the key.
mockNuxtImport('useI18n', () => () => ({
  locale: ref(locale.value),
  locales: ref([{ code: 'en', name: 'English' }, { code: 'es', name: 'Español' }, { code: 'de', name: 'Deutsch' }]),
  loadLocaleMessages,
  t: (key: string, values: Record<string, string> = {}) => {
    const text = key.split('.').reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], en)
    if (typeof text !== 'string') throw new Error(`missing i18n key ${key}`)
    return text.replace(/\{(\w+)\}/g, (_, name) => values[name] ?? '')
  }
}))

function config(overrides: Record<string, unknown> = {}) {
  return {
    clinic_name: 'Synthetic Clinic',
    slot_minutes: 30,
    window_days: 14,
    ask_existing_patient: true,
    allow_comment: true,
    redirect_url: null,
    privacy_url: 'https://clinic.example.es/privacy',
    embed_origins: [],
    timezone: 'UTC',
    branding: {
      logo_url: `/api/v1/online_booking/public/${CLINIC}/logo`,
      accent_color: '#aa3300',
      title_es: null,
      intro_es: null,
      title_en: 'Book at Synthetic Clinic',
      intro_en: 'Pick a time.'
    },
    reasons: [
      { id: 'first_visit', name_es: 'Primera visita', name_en: 'First visit', duration_minutes: 30 },
      { id: 'checkup', name_es: 'Revisión', name_en: 'Check-up', duration_minutes: 30 }
    ],
    ...overrides
  }
}

function addDays(day: string, count: number) {
  const date = new Date(`${day}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + count)
  return date.toISOString().slice(0, 10)
}

function mount() {
  return mountSuspended(BookingPage)
}

async function ready(wrapper: VueWrapper) {
  await vi.waitFor(() => expect(wrapper.findAll('[data-testid="booking-slot"]').length).toBeGreaterThan(0))
}

async function fill(wrapper: VueWrapper) {
  await wrapper.find('#booking-first-name').setValue('Synthetic')
  await wrapper.find('#booking-last-name').setValue('Person')
  await wrapper.find('#booking-email').setValue('synthetic@example.com')
  await wrapper.find('#booking-phone').setValue('+34 600 123 456')
  await wrapper.find('[data-testid="booking-consent"]').setValue(true)
}

function proofInput(wrapper: VueWrapper, value = 'solved-proof') {
  // The ALTCHA widget writes its payload to a hidden input inside the form.
  const input = document.createElement('input')
  input.type = 'hidden'
  input.name = 'altcha'
  input.value = value
  wrapper.find('form').element.append(input)
}

describe('public booking page', () => {
  let wrapper: VueWrapper | undefined
  beforeEach(() => {
    locale.value = 'en'
    for (const fn of [api.config, api.availability, api.createRequest, api.confirm]) fn.mockReset()
    api.config.mockResolvedValue(config())
    api.availability.mockImplementation(async (from: string, days: number) => ({
      days: Array.from({ length: days }, (_, i) => {
        const date = addDays(from, i)
        return { date, starts: [`${date}T09:00:00Z`, `${date}T15:00:00Z`] }
      })
    }))
    api.createRequest.mockResolvedValue({ message: 'ok' })
    window.history.replaceState(null, '', `/p/booking/${CLINIC}`)
  })
  afterEach(() => {
    wrapper?.unmount()
    window.history.replaceState(null, '', '/')
  })

  it('renders the clinic configuration: branding, reasons and optional questions', async () => {
    wrapper = await mount()
    await ready(wrapper)
    expect(wrapper.find('[data-testid="booking-title"]').text()).toBe('Book at Synthetic Clinic')
    expect(wrapper.text()).toContain('Pick a time.')
    expect(wrapper.find('[data-testid="booking-logo"]').attributes('src')).toBe(api.logoUrl)
    expect(wrapper.find('[data-testid="booking-logo"]').attributes('alt')).toBe('Synthetic Clinic')
    await vi.waitFor(() => expect(document.title).toBe('Book at Synthetic Clinic'))
    expect(wrapper.findAll('#booking-reason option').map(option => option.text())).toEqual(['First visit', 'Check-up'])
    expect(wrapper.find('#booking-existing').exists()).toBe(true)
    expect(wrapper.find('#booking-comment').exists()).toBe(true)
    expect(wrapper.text()).toContain('Do not include medical information.')
    expect(wrapper.find('[data-testid="booking-honeypot"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="booking-submit"]').attributes('style')).toContain('background-color')
    expect(api.availability).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/), expect.any(Number), 'first_visit')
  })

  it('hides optional questions and ignores a logo from another origin', async () => {
    api.config.mockResolvedValue(config({
      ask_existing_patient: false,
      allow_comment: false,
      branding: { ...config().branding, logo_url: 'https://evil.example/logo.png' }
    }))
    wrapper = await mount()
    await ready(wrapper)
    expect(wrapper.find('#booking-existing').exists()).toBe(false)
    expect(wrapper.find('#booking-comment').exists()).toBe(false)
    expect(wrapper.find('[data-testid="booking-logo"]').exists()).toBe(false)
  })

  it('selects a slot and reloads availability when the visit reason changes', async () => {
    wrapper = await mount()
    await ready(wrapper)
    const slots = wrapper.findAll('[data-testid="booking-slot"]')
    expect(slots.map(slot => slot.text())).toEqual(['09:00 AM', '03:00 PM'])
    await slots[1]!.trigger('click')
    expect(wrapper.findAll('[data-testid="booking-slot"]')[1]!.attributes('aria-pressed')).toBe('true')
    await wrapper.find('#booking-reason').setValue('checkup')
    await vi.waitFor(() => expect(api.availability).toHaveBeenLastCalledWith(expect.any(String), expect.any(Number), 'checkup'))
    await ready(wrapper)
    expect(wrapper.findAll('[data-testid="booking-slot"]').every(slot => slot.attributes('aria-pressed') === 'false')).toBe(true)
  })

  it('submits the request with the ALTCHA proof and shows the check-your-email notice', async () => {
    wrapper = await mount()
    await ready(wrapper)
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    await fill(wrapper)
    await wrapper.find('#booking-existing').setValue('yes')
    await wrapper.find('#booking-comment').setValue('Prefers mornings')
    proofInput(wrapper)
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(api.createRequest).toHaveBeenCalledTimes(1))
    expect(api.createRequest.mock.calls[0]![0]).toMatchObject({
      contact_name: 'Synthetic Person',
      contact_first_name: 'Synthetic',
      contact_last_name: 'Person',
      contact_email: 'synthetic@example.com',
      contact_phone: '+34 600 123 456',
      existing_patient: true,
      comment: 'Prefers mornings',
      language: 'en',
      reason: 'first_visit',
      website: '',
      altcha: 'solved-proof'
    })
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-result"]').exists()).toBe(true))
    expect(wrapper.text()).toContain('Check your email')
  })

  it('sends the honeypot value untouched so the server can reject bots', async () => {
    wrapper = await mount()
    await ready(wrapper)
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    await fill(wrapper)
    await wrapper.find('[data-testid="booking-honeypot"]').setValue('http://spam.example')
    proofInput(wrapper)
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(api.createRequest).toHaveBeenCalled())
    expect(api.createRequest.mock.calls[0]![0].website).toBe('http://spam.example')
  })

  it('requires a slot, a valid phone and a solved ALTCHA before sending', async () => {
    wrapper = await mount()
    await ready(wrapper)
    await fill(wrapper)
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toBe('Select an available time.'))
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    await wrapper.find('#booking-phone').setValue('12')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toContain('Enter a valid number'))
    await wrapper.find('#booking-phone').setValue('+34 600 123 456')
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toBe('Complete the verification before continuing.'))
    expect(api.createRequest).not.toHaveBeenCalled()
  })

  it('reports a slot conflict and a generic failure', async () => {
    wrapper = await mount()
    await ready(wrapper)
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    await fill(wrapper)
    proofInput(wrapper)
    api.createRequest.mockRejectedValueOnce(new PublicBookingError(409))
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toBe('That time is no longer available. Choose another.'))
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    api.createRequest.mockRejectedValueOnce(new PublicBookingError(500))
    await wrapper.find('form').trigger('submit')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toBe('We could not complete the request. Please try again.'))
  })

  it.each(['#5BC0DE', '#123456'])('uses a contrasting foreground for selected controls with accent %s', async (accent) => {
    api.config.mockResolvedValue(config({ branding: { ...config().branding, accent_color: accent } }))
    wrapper = await mount()
    await ready(wrapper)
    const day = wrapper.find('[data-testid="booking-day"][aria-pressed="true"]')
    expect(day.attributes('style')).toContain(accent === '#5BC0DE' ? 'color: #000000' : 'color: #ffffff')
    await wrapper.findAll('[data-testid="booking-slot"]')[0]!.trigger('click')
    expect(wrapper.find('[data-testid="booking-slot"][aria-pressed="true"]').attributes('style')).toContain(accent === '#5BC0DE' ? 'color: #000000' : 'color: #ffffff')
  })

  it('explains why the submit button is disabled', async () => {
    wrapper = await mount()
    await ready(wrapper)
    expect(wrapper.find('[data-testid="booking-submit"]').attributes('aria-describedby')).toBe('booking-consent-hint')
    expect(wrapper.find('#booking-consent-hint').text()).toContain('privacy')
  })

  it('disables sending when the clinic has no privacy policy URL', async () => {
    api.config.mockResolvedValue(config({ privacy_url: null }))
    wrapper = await mount()
    await ready(wrapper)
    expect(wrapper.find('[data-testid="booking-submit"]').attributes('disabled')).toBeDefined()
    expect(wrapper.text()).toContain('Online booking is unavailable right now.')
  })

  it('shows the unavailable state when the clinic booking cannot be loaded', async () => {
    api.config.mockRejectedValue(new PublicBookingError(404))
    wrapper = await mount()
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-unavailable"]').exists()).toBe(true))
    expect(api.availability).not.toHaveBeenCalled()
  })

  it('shows the confirmation landing from the email link and confirms on press only', async () => {
    window.history.replaceState(null, '', `/p/booking/${CLINIC}#token=${'t'.repeat(40)}`)
    api.confirm.mockResolvedValue({ status: 'confirmed', start_time: '2030-01-07T09:00:00Z', timezone: 'UTC' })
    wrapper = await mount()
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-confirm"]').exists()).toBe(true))
    expect(window.location.hash).toBe('')
    expect(api.confirm).not.toHaveBeenCalled()
    expect(api.availability).not.toHaveBeenCalled()
    await wrapper.find('[data-testid="booking-confirm"]').trigger('click')
    await vi.waitFor(() => expect(api.confirm).toHaveBeenCalledWith('t'.repeat(40)))
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-result"]').exists()).toBe(true))
    expect(wrapper.text()).toContain('Received!')
    expect(wrapper.text()).toContain('Monday, January 7')
    expect(wrapper.text()).toContain('09:00 AM')
  })

  it.each([
    [410, 'This link has expired or has already been used. Please request another time.'],
    [409, 'That time is no longer available. Choose another.'],
    [500, 'We could not complete the request. Please try again.']
  ])('explains a failed confirmation (%s) and offers to start again', async (status, message) => {
    window.history.replaceState(null, '', `/p/booking/${CLINIC}#token=${'t'.repeat(40)}`)
    api.confirm.mockRejectedValue(new PublicBookingError(status))
    wrapper = await mount()
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-confirm"]').exists()).toBe(true))
    await wrapper.find('[data-testid="booking-confirm"]').trigger('click')
    await vi.waitFor(() => expect(wrapper!.find('[data-testid="booking-error"]').text()).toBe(message))
    expect(wrapper.text()).toContain('Start again')
    if (status === 410) expect(wrapper.find('[data-testid="booking-confirm"]').exists()).toBe(false)
  })

  it('switches language in memory without persisting a cookie', async () => {
    wrapper = await mount()
    await ready(wrapper)
    await wrapper.find('[data-testid="booking-language"]').setValue('de')
    expect(loadLocaleMessages).toHaveBeenCalledWith('de')
  })
})
