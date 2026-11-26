// @vitest-environment node
import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { teWithFallback, timelineEntryTitle } from '#module-layers/patient_timeline/frontend/utils/timelineTitle'

/**
 * #1174: timeline headings were printed from the stored (Spanish) `title`.
 * They are now rebuilt from event_type + event_data through the real locale
 * files, with the stored title as the fallback for old rows.
 */

type Tree = Record<string, unknown>

// Read the locale files off disk: importing them goes through the i18n
// plugin, which compiles messages into functions.
function load(locale: string): Tree {
  return JSON.parse(readFileSync(resolve(__dirname, `../../i18n/locales/${locale}.json`), 'utf-8')) as Tree
}

function lookup(messages: Tree, key: string): string | undefined {
  let node: unknown = messages
  for (const part of key.split('.')) {
    if (node === null || typeof node !== 'object') return undefined
    node = (node as Tree)[part]
  }
  return typeof node === 'string' ? node : undefined
}

function i18nFor(messages: Tree) {
  return {
    t: (key: string, params: Record<string, unknown> = {}) => {
      const message = lookup(messages, key)
      if (message === undefined) throw new Error(`missing i18n key ${key}`)
      return message.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name]))
    },
    te: (key: string) => lookup(messages, key) !== undefined
  }
}

const EN = i18nFor(load('en'))
const ES = i18nFor(load('es'))
const HU = i18nFor(load('hu'))

function entry(event_type: string, title: string, event_data?: Record<string, unknown>) {
  return { event_type, title, event_data }
}

describe('timelineEntryTitle', () => {
  it('renders a new appointment row in the viewer language, not the stored Spanish', () => {
    const e = entry('appointment.scheduled', 'Cita programada: Limpieza', { treatment_type: 'Limpieza', cabinet: 'G1' })
    expect(timelineEntryTitle(e, EN)).toBe('Appointment scheduled: Limpieza')
    expect(timelineEntryTitle(e, HU)).toBe('Időpont lefoglalva: Limpieza')
  })

  it('uses a translated default when the appointment had no treatment type', () => {
    const e = entry('appointment.checked_in', 'Paciente llegó a la clínica (Consulta)', { treatment_type: null })
    expect(timelineEntryTitle(e, EN)).toBe('Patient arrived at the clinic (Consultation)')
  })

  it('falls back to the stored title for an old row without the dynamic field', () => {
    const e = entry('appointment.scheduled', 'Cita programada: Limpieza', { cabinet: 'G1' })
    expect(timelineEntryTitle(e, EN)).toBe('Cita programada: Limpieza')
  })

  it('falls back to the stored title for an unknown event type', () => {
    expect(timelineEntryTitle(entry('email.sent', 'Email enviado: hola', {}), EN)).toBe('Email enviado: hola')
  })

  it('keeps medical updates on the stored summary (free text from the producer)', () => {
    const e = entry('patient.medical_updated', 'Nueva alergia a penicilina', { section: 'allergies' })
    expect(timelineEntryTitle(e, EN)).toBe('Nueva alergia a penicilina')
  })

  it('translates budget and invoice rows from the number already in event_data', () => {
    expect(timelineEntryTitle(entry('budget.sent', 'Presupuesto enviado: P-1', { budget_number: 'P-1' }), EN))
      .toBe('Estimate sent: P-1')
    expect(timelineEntryTitle(entry('budget.accepted', 'Presupuesto aceptado', { budget_number: null }), EN))
      .toBe('Estimate accepted')
    expect(timelineEntryTitle(entry('invoice.paid', 'Factura pagada: F-9', { invoice_number: 'F-9', total: 10 }), EN))
      .toBe('Invoice paid: F-9')
  })

  it('translates static titles that need no event_data', () => {
    expect(timelineEntryTitle(entry('prescription.issued', 'Receta emitida'), EN)).toBe('Prescription issued')
    expect(timelineEntryTitle(entry('orthodontics.control_registered', 'Control de ortodoncia'), EN))
      .toBe('Orthodontic check-up')
  })

  it('translates the plan closure reason when a label exists, raw otherwise', () => {
    expect(timelineEntryTitle(entry('treatment_plan.closed', 'Plan cerrado (expired)', { closure_reason: 'expired' }), EN))
      .toBe('Plan closed (Expired)')
    expect(timelineEntryTitle(entry('treatment_plan.closed', 'Plan cerrado (weird)', { closure_reason: 'weird' }), EN))
      .toBe('Plan closed (weird)')
  })

  it('builds channel + subject for notifications', () => {
    const sent = entry('notification.sent', 'WhatsApp enviado: budget_sent', {
      channel: 'whatsapp', template_key: 'budget_sent', subject: null
    })
    expect(timelineEntryTitle(sent, EN)).toBe('WhatsApp sent: budget_sent')
    const failed = entry('notification.failed', 'Email fallido: Hola', { channel: 'email', subject: 'Hola' })
    expect(timelineEntryTitle(failed, EN)).toBe('Email failed: Hola')
  })

  it('builds clinical note titles from note_type and tooth', () => {
    const e = entry('clinical_notes.diagnosis_created', 'Nota de diagnóstico (diente 16)', {
      note_type: 'diagnosis', tooth_number: 16
    })
    expect(timelineEntryTitle(e, EN)).toBe('Diagnosis note (tooth 16)')
  })

  it('distinguishes X-rays from photos', () => {
    const e = entry('media.photo_uploaded', 'Radiografía: Pano', { media_kind: 'xray', document_title: 'Pano' })
    expect(timelineEntryTitle(e, EN)).toBe('X-ray: Pano')
  })

  it('reproduces the stored Spanish titles in the es locale', () => {
    const cases: Array<[string, string, Record<string, unknown>]> = [
      ['appointment.no_show', 'Paciente no asistió: Revisión', { treatment_type: 'Revisión' }],
      ['odontogram.treatment.performed', 'Tratamiento realizado: Obturación', { treatment_name: 'Obturación', clinical_type: 'restoration' }],
      ['treatment_plan.item_completed_without_note', 'Empaste 16 completado sin nota', { item_name: 'Empaste 16' }],
      ['budget.reminder_sent', 'Recordatorio enviado (7d)', { milestone_days: 7 }],
      ['document.uploaded', 'Documento: Consentimiento', { document_title: 'Consentimiento' }]
    ]
    for (const [type, stored, data] of cases) {
      expect(timelineEntryTitle(entry(type, 'STORED', data), ES)).toBe(stored)
    }
  })
})

describe('teWithFallback', () => {
  it('finds a closure reason for pt-BR through its pt fallback', () => {
    const PT = load('pt')
    const known: Record<string, Tree> = { 'pt': PT, 'pt-BR': {} }
    // vue-i18n's te(key) looks at the current locale only.
    const te = (key: string, l = 'pt-BR') => lookup(known[l] ?? {}, key) !== undefined
    const fallback = { 'pt-BR': ['pt', 'en'] }
    expect(te('treatmentPlans.closureReason.expired')).toBe(false)
    expect(teWithFallback(te, 'pt-BR', fallback)('treatmentPlans.closureReason.expired')).toBe(true)
    expect(teWithFallback(te, 'pt-BR', fallback)('treatmentPlans.closureReason.nope')).toBe(false)
  })
})
