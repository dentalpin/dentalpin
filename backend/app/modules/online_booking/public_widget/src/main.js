import 'altcha/i18n'
import { isValidPhoneNumber } from 'libphonenumber-js/max'
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
    phone: 'Teléfono',
    phoneHint:
      'Introduce un número válido, con prefijo internacional si no es español.',
    selectDay: 'Selecciona un día disponible.', weekEmpty: 'No hay huecos esta semana.',
    morning: 'Mañana',
    afternoon: 'Tarde',
    previousWeek: 'Semana anterior',
    nextWeek: 'Semana siguiente',
    restart: 'Volver a empezar',
    noAvailable: 'No hay citas disponibles en las próximas semanas.',
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
    phone: 'Phone number',
    phoneHint:
      'Enter a valid number, including the country code outside Spain.',
    selectDay: 'Select an available day.', weekEmpty: 'There are no available times this week.',
    morning: 'Morning',
    afternoon: 'Afternoon',
    previousWeek: 'Previous week',
    nextWeek: 'Next week',
    restart: 'Start again',
    noAvailable: 'There are no available appointments in the coming weeks.',
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
let resultStart = ''
let branding = {}
let trustedLogo = ''
let daysByDate = new Map()
let firstDay = ''
let weekOffset = 0
let maxDays = 0
let chosenDay = ''
const clinicId = String(cfg.clinicId || '')
const validClinic = validClinicId(clinicId)
const base = `/api/v1/online_booking/public/${encodeURIComponent(clinicId)}`
const t = key => copy[language][key] || key
const node = id => document.getElementById(id)
const error = (message) => {
  const element = node('error')
  if (element) element.textContent = message
  const restart = node('restart')
  if (restart) restart.classList.toggle('hidden', !message)
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
  const logo = trustedLogo
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
      `<section class="panel"><h1>${t('confirm')}</h1><p>${t('confirmIntro')}</p><p id="error" class="error" role="alert"></p><button class="primary" id="confirm">${t('confirmButton')}</button> <a id="restart" class="hidden" href="${location.pathname}">${t('restart')}</a></section>`
    )
    node('confirm').onclick = async (e) => {
      e.target.disabled = true
      try {
        const response = await api('/confirm', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ token })
        })
        resultStart = response.data.start_time
        timezone = response.data.timezone || timezone
        token = null
        state = 'confirmed'
        render()
      } catch (err) {
        error(err.status === 410 ? t('expired') : err.status === 409 ? t('conflict') : t('error'))
        node('restart').classList.remove('hidden')
        e.target.disabled = false
      }
    }
    return
  }
  if (state === 'confirmed' || state === 'queued') {
    frame(
      `<section class="panel"><h1 id="result-title"></h1><p id="result-body"></p><a href="${location.pathname}">${t('restart')}</a></section>`
    )
    node('result-title').textContent
      = state === 'confirmed'
        ? language === 'es'
          ? '¡Recibido!'
          : 'Received!'
        : t('queued')
    const value = state === 'confirmed' ? resultStart : selected
    const date = new Date(value)
    const day = new Intl.DateTimeFormat(language, {
      timeZone: timezone,
      weekday: 'long',
      day: 'numeric',
      month: 'long'
    }).format(date)
    const hour = new Intl.DateTimeFormat(language, {
      timeZone: timezone,
      hour: '2-digit',
      minute: '2-digit'
    }).format(date)
    node('result-body').textContent
      = state === 'confirmed'
        ? language === 'es'
          ? `Te contactaremos para confirmar tu cita del ${day} a las ${hour}.`
          : `We will contact you to confirm your appointment on ${day} at ${hour}.`
        : `${t('queuedBody')} ${day}, ${hour}.`
    return
  }
  selected = ''
  frame(
    `<div class="hero"><h1 id="hero-title"></h1><p id="hero-intro"></p></div><section class="panel"><h2>1. ${t('choose')}</h2><div class="grid"><div><label for="reason">${t('reason')}</label><select id="reason"></select></div><div></div></div><div class="calendar-header"><button type="button" id="previous-week" aria-label="${t('previousWeek')}">‹</button><strong id="week-label"></strong><button type="button" id="next-week" aria-label="${t('nextWeek')}">›</button></div><div id="calendar" class="calendar" aria-label="${t('date')}"></div><h3>${t('slots')}</h3><p id="slot-message" class="note"></p><div id="slots" class="slots"></div></section><form id="form" class="panel"><h2>2. ${t('contact')}</h2><div class="grid"><div><label for="name">${t('name')}</label><input id="name" autocomplete="name" maxlength="120" required></div><div><label for="email">${t('email')}</label><input id="email" type="email" autocomplete="email" maxlength="254" required></div></div><label for="phone">${t('phone')}</label><input id="phone" type="tel" autocomplete="tel" maxlength="30" required aria-describedby="phone-hint"><small id="phone-hint">${t('phoneHint')}</small><input id="website" class="website" tabindex="-1" autocomplete="off" aria-hidden="true"><p class="note"><label class="consent"><input id="consent" type="checkbox" required><span><a id="privacy" target="_blank" rel="noopener noreferrer">${t('privacy')}</a></span></label></p><altcha-widget id="altcha" name="altcha" language="${language}"></altcha-widget><p id="error" class="error" role="alert"></p><a id="restart" class="hidden" href="${location.pathname}">${t('restart')}</a> <button id="submit" class="primary" type="submit">${t('submit')}</button></form>`
  )
  node('hero-title').textContent = branding[`title_${language}`] || t('title')
  node('hero-intro').textContent = branding[`intro_${language}`] || t('intro')
  const privacy = cfg.privacyUrl && safeUrl(cfg.privacyUrl, location.href)
  if (!privacy) {
    node('submit').disabled = true
    error(t('unavailable'))
    return
  }
  node('privacy').href = privacy
  node('altcha').setAttribute('challenge', `${base}/challenge`)
  node('previous-week').onclick = () => {
    weekOffset = Math.max(0, weekOffset - 7)
    drawCalendar()
  }
  node('next-week').onclick = async () => {
    const next = weekOffset + 7
    node('next-week').disabled = true
    try {
      await ensureDays(next, 7)
      weekOffset = next
      drawCalendar()
    } catch {
      error(t('error'))
      node('next-week').disabled = false
    }
  }
  node('phone').onblur = () => {
    const value = node('phone').value.trim()
    if (value && !isValidPhoneNumber(value, 'ES')) error(t('phoneHint'))
  }
  node('form').onsubmit = submit
  api('/config')
    .then(async (response) => {
      timezone = response.data.timezone
      branding = response.data.branding || {}
      trustedLogo = branding.logo_url === `${base}/logo` ? `${base}/logo` : ''
      cfg.accentColor = branding.accent_color || '#127f83'
      if (!trustedLogo) node('logo').classList.add('hidden')
      document.documentElement.style.setProperty('--accent', cfg.accentColor)
      node('hero-title').textContent
        = branding[`title_${language}`] || t('title')
      node('hero-intro').textContent
        = branding[`intro_${language}`] || t('intro')
      if (trustedLogo) {
        node('logo').src = trustedLogo
        node('logo').alt = String(cfg.clinicName || '')
        node('logo').classList.remove('hidden')
      }
      if (/^#[0-9a-f]{6}$/i.test(branding.accent_color || ''))
        document.documentElement.style.setProperty(
          '--accent',
          branding.accent_color
        )
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit'
      }).formatToParts(new Date())
      const part = name => parts.find(item => item.type === name)?.value
      firstDay = `${part('year')}-${part('month')}-${part('day')}`
      maxDays = response.data.window_days + 1
      const reasonSelect = node('reason')
      reasonSelect.replaceChildren()
      for (const reason of response.data.reasons) {
        const option = document.createElement('option')
        option.value = reason.id
        option.textContent = reason[`name_${language}`]
        reasonSelect.append(option)
      }
      if (!reasonSelect.options.length) throw new Error('No active visit reasons')
      reasonSelect.onchange = () => refreshAvailability().catch(() => error(t('error')))
      await refreshAvailability()
    })
    .catch(() => {
      node('submit').disabled = true
      error(t('unavailable'))
    })
}
async function refreshAvailability() {
  const selector = node('reason')
  selector.disabled = true
  selected = ''
  chosenDay = ''
  daysByDate = new Map()
  weekOffset = 0
  node('slot-message').textContent = t('loading')
  try {
    for (let offset = 0; offset < maxDays; offset += 31) {
      await ensureDays(offset, Math.min(31, maxDays - offset))
      const first = [...daysByDate.entries()].find(([, starts]) => starts.length)
      if (first) {
        chosenDay = first[0]
        weekOffset = Math.floor(dayDistance(firstDay, chosenDay) / 7) * 7
        break
      }
    }
    drawCalendar()
  } finally {
    selector.disabled = false
  }
}
function offsetDay(day, offset) {
  const date = new Date(`${day}T12:00:00Z`)
  date.setUTCDate(date.getUTCDate() + offset)
  return date.toISOString().slice(0, 10)
}
function dayDistance(a, b) {
  return Math.round(
    (Date.parse(`${b}T12:00:00Z`) - Date.parse(`${a}T12:00:00Z`)) / 86400000
  )
}
async function ensureDays(offset, count) {
  if (offset >= maxDays) return
  const first = offsetDay(firstDay, offset)
  const response = await api(
    `/availability?from_day=${first}&days=${Math.min(count, maxDays - offset)}&reason=${encodeURIComponent(node('reason').value)}`
  )
  for (const day of response.data.days) daysByDate.set(day.date, day.starts)
}
function drawCalendar() {
  const calendar = node('calendar')
  if (!calendar) return
  calendar.replaceChildren()
  node('previous-week').disabled = weekOffset === 0
  node('next-week').disabled = weekOffset + 7 >= maxDays
  const begin = offsetDay(firstDay, weekOffset)
  const end = offsetDay(firstDay, Math.min(weekOffset + 6, maxDays - 1))
  const fmt = new Intl.DateTimeFormat(language, {
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC'
  })
  node('week-label').textContent
    = `${fmt.format(new Date(`${begin}T12:00:00Z`))} – ${fmt.format(new Date(`${end}T12:00:00Z`))}`
  for (let i = 0; i < 7 && weekOffset + i < maxDays; i++) {
    const day = offsetDay(firstDay, weekOffset + i)
    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'calendar-day'
    button.disabled = !(daysByDate.get(day) || []).length
    button.setAttribute('aria-pressed', String(day === chosenDay))
    button.textContent = new Intl.DateTimeFormat(language, {
      weekday: 'short',
      day: 'numeric',
      timeZone: 'UTC'
    }).format(new Date(`${day}T12:00:00Z`))
    button.onclick = () => {
      chosenDay = day
      selected = ''
      drawCalendar()
    }
    calendar.append(button)
  }
  drawSlots()
}
function drawSlots() {
  const container = node('slots')
  container.replaceChildren()
  const visible
    = dayDistance(firstDay, chosenDay) >= weekOffset
      && dayDistance(firstDay, chosenDay) < weekOffset + 7
  const values = visible ? daysByDate.get(chosenDay) || [] : []
  const weekHasSlots = Array.from({ length: Math.min(7, maxDays - weekOffset) }, (_, i) => daysByDate.get(offsetDay(firstDay, weekOffset + i)) || []).some(items => items.length)
  node('slot-message').textContent = values.length ? '' : t(weekHasSlots ? 'selectDay' : 'weekEmpty')
  for (const [key, predicate] of [
    ['morning', h => h < 12],
    ['afternoon', h => h >= 12]
  ]) {
    const starts = values.filter(value =>
      predicate(
        Number(
          new Intl.DateTimeFormat('en-GB', {
            timeZone: timezone,
            hour: '2-digit',
            hourCycle: 'h23'
          }).format(new Date(value))
        )
      )
    )
    if (!starts.length) continue
    const group = document.createElement('section')
    group.className = 'slot-group'
    const heading = document.createElement('h4')
    heading.textContent = t(key)
    group.append(heading)
    const list = document.createElement('div')
    list.className = 'slots'
    for (const value of starts) {
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'slot'
      button.setAttribute('aria-pressed', String(value === selected))
      button.textContent = new Intl.DateTimeFormat(language, {
        timeZone: timezone,
        hour: '2-digit',
        minute: '2-digit'
      }).format(new Date(value))
      button.onclick = () => {
        selected = value
        drawSlots()
      }
      list.append(button)
    }
    group.append(list)
    container.append(group)
  }
}

async function submit(event) {
  event.preventDefault()
  error('')
  if (!selected) {
    error(t('selectSlot'))
    return
  }
  if (!isValidPhoneNumber(node('phone').value.trim(), 'ES')) {
    error(t('phoneHint'))
    node('phone').focus()
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
        contact_phone: node('phone').value.trim(),
        language,
        reason: node('reason').value,
        website: node('website').value,
        altcha
      })
    })
    state = 'queued'
    render()
  } catch (err) {
    node('altcha').reset()
    if (err.status === 409) {
      try {
        await ensureDays(weekOffset, 7)
        selected = ''
        drawCalendar()
      } catch {
        // Keep the existing calendar and report the conflict.
      }
    }
    error(err.status === 409 ? t('conflict') : t('error'))
    button.disabled = false
  }
}
render()
if (state === 'confirm') {
  api('/config')
    .then((response) => {
      const brand = response.data.branding || {}
      if (
        brand.logo_url === `${base}/logo`
        && node('logo')
      ) {
        trustedLogo = `${base}/logo`
        node('logo').src = trustedLogo
        node('logo').alt = String(cfg.clinicName || '')
        node('logo').classList.remove('hidden')
      }
      if (/^#[0-9a-f]{6}$/i.test(brand.accent_color || '')) {
        cfg.accentColor = brand.accent_color
        document.documentElement.style.setProperty(
          '--accent',
          brand.accent_color
        )
      }
    })
    .catch(() => {})
}
