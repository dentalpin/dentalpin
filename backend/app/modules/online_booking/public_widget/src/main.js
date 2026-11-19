import 'altcha/i18n'
import './style.css'
import { safeUrl, validClinicId } from './helpers.js'

const copy = {
  es: {
    title: 'Solicita tu cita online',
    intro:
      'Elige un hueco y déjanos tus datos. Te enviaremos un enlace para confirmar tu solicitud.',
    lang: 'Idioma',
    choose: 'Elige una fecha y un motivo',
    reason: 'Motivo de la visita',
    first_visit: 'Primera visita',
    checkup: 'Revisión',
    date: 'Fecha',
    slots: 'Horas disponibles',
    loading: 'Buscando huecos…',
    empty: 'No hay huecos disponibles para esta fecha.',
    contact: 'Tus datos de contacto',
    name: 'Nombre y apellidos',
    email: 'Correo electrónico',
    phone: 'Teléfono (opcional)',
    privacy: 'He leído la política de privacidad',
    submit: 'Enviar solicitud',
    confirm: 'Confirma tu solicitud',
    confirmIntro:
      'Pulsa el botón para confirmar la solicitud. Esta acción no crea una cita: recepción la revisará.',
    confirmButton: 'Confirmar solicitud',
    confirmed: 'Solicitud confirmada',
    confirmedBody:
      'Recepción revisará tu solicitud. La cita no está creada todavía.',
    queued: 'Revisa tu correo',
    queuedBody:
      'Si los datos son válidos, recibirás un enlace para confirmar la solicitud. Caduca en 10 minutos.',
    unavailable: 'La reserva online no está disponible en este momento.',
    error: 'No hemos podido completar la solicitud. Inténtalo de nuevo.',
    conflict: 'El hueco ya no está disponible. Elige otro.',
    expired: 'El enlace ha caducado o ya se ha utilizado. Solicita otro hueco.',
    selectSlot: 'Selecciona un hueco.',
    verify: 'Completa la verificación antes de continuar.'
  },
  en: {
    title: 'Request an appointment',
    intro:
      'Choose a time and leave your contact details. We will email you a link to confirm your request.',
    lang: 'Language',
    choose: 'Choose a date and visit type',
    reason: 'Visit type',
    first_visit: 'First visit',
    checkup: 'Check-up',
    date: 'Date',
    slots: 'Available times',
    loading: 'Looking for times…',
    empty: 'There are no available times for this date.',
    contact: 'Your contact details',
    name: 'Full name',
    email: 'Email address',
    phone: 'Phone (optional)',
    privacy: 'I have read the privacy policy',
    submit: 'Send request',
    confirm: 'Confirm your request',
    confirmIntro:
      'Select the button to confirm your request. This does not create an appointment: reception will review it.',
    confirmButton: 'Confirm request',
    confirmed: 'Request confirmed',
    confirmedBody:
      'Reception will review your request. Your appointment has not yet been created.',
    queued: 'Check your email',
    queuedBody:
      'If the details are valid, you will receive a link to confirm your request. It expires in 10 minutes.',
    unavailable: 'Online booking is unavailable right now.',
    error: 'We could not complete the request. Please try again.',
    conflict: 'That time is no longer available. Choose another.',
    expired:
      'This link has expired or has already been used. Please request another time.',
    selectSlot: 'Select an available time.',
    verify: 'Complete the verification before continuing.'
  }
}
const cfg = window.BOOKING_CONFIG || {}
let language = ['es', 'en'].includes(cfg.language) ? cfg.language : 'es'
const app = document.querySelector('#app')
let token = new URLSearchParams(location.hash.slice(1)).get('token')
if (location.hash)
  history.replaceState(null, '', location.pathname + location.search)
let selected = ''
let timezone = 'UTC'
let state = token ? 'confirm' : 'booking'
const clinicId = String(cfg.clinicId || '')
const validClinic = validClinicId(clinicId)
const base = `/api/v1/online_booking/public/${encodeURIComponent(clinicId)}`
const t = key => copy[language][key] || key
const node = id => document.getElementById(id)
const error = (message) => {
  const element = node('error')
  if (element) element.textContent = message
}
async function api(path, options = {}) {
  const res = await fetch(base + path, {
    cache: 'no-store',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
    ...options
  })
  if (!res.ok) {
    const e = new Error('request failed')
    e.status = res.status
    throw e
  }
  return res.json()
}
function frame(content) {
  app.innerHTML = `<header><div class="brand"><img id="logo" class="hidden" alt=""><span id="clinic"></span></div><label>${t('lang')} <select id="lang" aria-label="${t('lang')}"><option value="es">Español</option><option value="en">English</option></select></label></header>${content}`
  node('clinic').textContent = String(cfg.clinicName || '')
  node('lang').value = language
  node('lang').onchange = (e) => {
    language = e.target.value
    render()
  }
  const logo = cfg.logoUrl && safeUrl(cfg.logoUrl, location.href)
  if (logo) {
    node('logo').src = logo
    node('logo').alt = String(cfg.clinicName || '')
    node('logo').classList.remove('hidden')
  }
  if (/^#[0-9a-f]{6}$/i.test(cfg.accentColor || ''))
    document.documentElement.style.setProperty('--accent', cfg.accentColor)
  document.documentElement.lang = language
}
function render() {
  if (!validClinic) {
    frame(
      `<section class="panel"><p class="error">${t('unavailable')}</p></section>`
    )
    return
  }
  if (state === 'confirm') {
    frame(
      `<section class="panel"><h1>${t('confirm')}</h1><p>${t('confirmIntro')}</p><p id="error" class="error" role="alert"></p><button class="primary" id="confirm">${t('confirmButton')}</button></section>`
    )
    node('confirm').onclick = async (e) => {
      e.target.disabled = true
      try {
        await api('/confirm', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ token })
        })
        token = null
        state = 'confirmed'
        render()
      } catch (err) {
        error(err.status === 410 ? t('expired') : t('error'))
        e.target.disabled = false
      }
    }
    return
  }
  if (state === 'confirmed' || state === 'queued') {
    frame(
      `<section class="panel"><h1>${t(state)}</h1><p>${t(state + 'Body')}</p></section>`
    )
    return
  }
  selected = ''
  frame(
    `<div class="hero"><span class="eyebrow">${t('title')}</span><h1>${t('title')}</h1><p>${t('intro')}</p></div><section class="panel"><h2>1. ${t('choose')}</h2><div class="grid"><div><label for="reason">${t('reason')}</label><select id="reason"><option value="first_visit">${t('first_visit')}</option><option value="checkup">${t('checkup')}</option></select></div><div><label for="day">${t('date')}</label><input id="day" type="date" required></div></div><h3>${t('slots')}</h3><p id="slot-message" class="note"></p><div id="slots" class="slots"></div></section><form id="form" class="panel"><h2>2. ${t('contact')}</h2><div class="grid"><div><label for="name">${t('name')}</label><input id="name" autocomplete="name" maxlength="120" required></div><div><label for="email">${t('email')}</label><input id="email" type="email" autocomplete="email" maxlength="254" required></div></div><label for="phone">${t('phone')}</label><input id="phone" type="tel" autocomplete="tel" maxlength="20" pattern="[+0-9 ()-]*"><input id="website" class="website" tabindex="-1" autocomplete="off" aria-hidden="true"><p class="note"><label class="consent"><input id="consent" type="checkbox" required><span><a id="privacy" target="_blank" rel="noopener noreferrer">${t('privacy')}</a></span></label></p><altcha-widget id="altcha" name="altcha" language="${language}"></altcha-widget><p id="error" class="error" role="alert"></p><button id="submit" class="primary" type="submit">${t('submit')}</button></form>`
  )
  const privacy = cfg.privacyUrl && safeUrl(cfg.privacyUrl, location.href)
  if (!privacy) {
    node('submit').disabled = true
    error(t('unavailable'))
    return
  }
  node('privacy').href = privacy
  node('altcha').setAttribute('challenge', `${base}/challenge`)
  node('day').onchange = loadSlots
  node('form').onsubmit = submit
  api('/config')
    .then((response) => {
      timezone = response.data.timezone
      if (!node('day')) return
      node('day').min = new Intl.DateTimeFormat('en-CA', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }).format(new Date())
    })
    .catch(() => {
      node('submit').disabled = true
      error(t('unavailable'))
    })
}
async function loadSlots() {
  selected = ''
  error('')
  node('slots').replaceChildren()
  node('slot-message').textContent = t('loading')
  const day = node('day').value
  try {
    const result = await api(`/availability?day=${encodeURIComponent(day)}`)
    if (node('day').value !== day) return
    node('slot-message').textContent = result.data.starts.length
      ? ''
      : t('empty')
    for (const value of result.data.starts) {
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'slot'
      button.setAttribute('aria-pressed', 'false')
      button.textContent = new Intl.DateTimeFormat(language, {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit'
      }).format(new Date(value))
      button.onclick = () => {
        selected = value
        for (const item of node('slots').children)
          item.setAttribute('aria-pressed', String(item === button))
      }
      node('slots').append(button)
    }
  } catch {
    node('slot-message').textContent = t('error')
  }
}
async function submit(event) {
  event.preventDefault()
  error('')
  if (!selected) {
    error(t('selectSlot'))
    return
  }
  const altcha = new FormData(node('form')).get('altcha')
  if (!altcha) {
    error(t('verify'))
    return
  }
  const button = node('submit')
  button.disabled = true
  try {
    await api('/requests', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        start_time: selected,
        contact_name: node('name').value.trim(),
        contact_email: node('email').value.trim(),
        contact_phone: node('phone').value.trim() || null,
        reason: node('reason').value,
        website: node('website').value,
        altcha
      })
    })
    state = 'queued'
    render()
  } catch (err) {
    node('altcha').reset()
    if (err.status === 409) await loadSlots()
    error(err.status === 409 ? t('conflict') : t('error'))
    button.disabled = false
  }
}
render()
