import type { TimelineEntry } from '~~/app/types'

/**
 * Build the heading of a timeline entry in the viewer's language (#1174).
 *
 * The backend stores a Spanish `title` on every row (it is the record, and
 * the agent tool reads it). The UI must not print it as-is, so the heading
 * is rebuilt from `event_type` + `event_data` through i18n.
 *
 * Falls back to the stored `title` when the event type is unknown, or when
 * the row predates the `event_data` field that carries the dynamic part of
 * the heading (treatment, item or plan name, message subject, document
 * title). Checking "key present" rather than "value truthy" matters: a new
 * row may carry an explicit `null` (no treatment type on the appointment),
 * an old row has no key at all and its only copy of the value is the
 * stored title.
 */

type Translate = (key: string, params?: Record<string, unknown>) => string

export interface TimelineTitleI18n {
  t: Translate
  te: (key: string) => boolean
}

type Entry = Pick<TimelineEntry, 'event_type' | 'title' | 'event_data'>

function str(value: unknown): string | null {
  if (typeof value === 'string' && value.trim() !== '') return value
  if (typeof value === 'number' && isFinite(value)) return String(value)
  return null
}

type FallbackLocale = string | string[] | Record<string, string[]> | false | undefined

/**
 * vue-i18n's `te(key)` checks the current locale only, ignoring the
 * fallback chain, so an overlay locale such as pt-BR (which falls back
 * to pt) reports a key it can translate as missing. This `te` also
 * checks the fallback locales.
 */
export function teWithFallback(
  te: (key: string, locale?: string) => boolean,
  locale: string,
  fallbackLocale: FallbackLocale
): (key: string) => boolean {
  let chain: string[] = []
  if (typeof fallbackLocale === 'string') chain = [fallbackLocale]
  else if (Array.isArray(fallbackLocale)) chain = fallbackLocale
  else if (fallbackLocale) chain = fallbackLocale[locale] ?? fallbackLocale.default ?? []
  return (key: string) => te(key) || chain.some(l => te(key, l))
}

export function timelineEntryTitle(entry: Entry, { t, te }: TimelineTitleI18n): string {
  const data = (entry.event_data ?? {}) as Record<string, unknown>
  const has = (key: string) => Object.prototype.hasOwnProperty.call(data, key)

  // Appointment lifecycle: the treatment name is dynamic.
  const treatment = () => str(data.treatment_type) ?? t('patients.timeline.titles.defaultTreatment')

  // Budgets / invoices / plans: an optional number, present in event_data
  // since the handlers were written.
  const numbered = (key: string, plain: string, withValue: string): string | null => {
    if (!has(key)) return null
    const value = str(data[key])
    return value ? t(withValue, { value }) : t(plain)
  }

  let title: string | null = null
  switch (entry.event_type) {
    case 'appointment.scheduled':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentScheduled', { treatment: treatment() })
      break
    case 'appointment.completed':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentCompleted', { treatment: treatment() })
      break
    case 'appointment.cancelled':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentCancelled', { treatment: treatment() })
      break
    case 'appointment.no_show':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentNoShow', { treatment: treatment() })
      break
    case 'appointment.confirmed':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentConfirmed', { treatment: treatment() })
      break
    case 'appointment.checked_in':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentCheckedIn', { treatment: treatment() })
      break
    case 'appointment.in_treatment':
      if (has('treatment_type')) title = t('patients.timeline.titles.appointmentInTreatment', { treatment: treatment() })
      break

    case 'odontogram.treatment.performed':
      if (has('treatment_name')) {
        const name = str(data.treatment_name) ?? str(data.clinical_type)
        title = name
          ? t('patients.timeline.titles.treatmentPerformedNamed', { name })
          : t('patients.timeline.titles.treatmentPerformed')
      }
      break
    case 'treatment_plan.created':
      if (has('plan_name')) {
        const name = str(data.plan_name) ?? str(data.plan_number)
        title = name
          ? t('patients.timeline.titles.planCreatedNamed', { name })
          : t('patients.timeline.titles.planCreated')
      }
      break
    case 'treatment_plan.treatment_completed':
      if (has('item_name')) {
        const name = str(data.item_name)
        title = name
          ? t('patients.timeline.titles.planItemCompletedNamed', { name })
          : t('patients.timeline.titles.planItemCompleted')
      }
      break
    case 'treatment_plan.item_completed_without_note':
      if (has('item_name')) {
        title = t('patients.timeline.titles.itemCompletedWithoutNote', {
          name: str(data.item_name) ?? t('patients.timeline.titles.defaultItem')
        })
      }
      break
    case 'treatment_plan.confirmed':
      title = numbered('plan_number', 'patients.timeline.titles.planConfirmed', 'patients.timeline.titles.planConfirmedNumbered')
      break
    case 'treatment_plan.closed':
      if (has('closure_reason')) {
        const raw = str(data.closure_reason) ?? 'other'
        const reasonKey = `treatmentPlans.closureReason.${raw}`
        title = t('patients.timeline.titles.planClosed', { reason: te(reasonKey) ? t(reasonKey) : raw })
      }
      break
    case 'treatment_plan.reactivated':
      title = t('patients.timeline.titles.planReactivated')
      break

    case 'budget.sent':
      title = numbered('budget_number', 'patients.timeline.titles.budgetSent', 'patients.timeline.titles.budgetSentNumbered')
      break
    case 'budget.accepted':
      title = numbered('budget_number', 'patients.timeline.titles.budgetAccepted', 'patients.timeline.titles.budgetAcceptedNumbered')
      break
    case 'budget.rejected':
      title = numbered('budget_number', 'patients.timeline.titles.budgetRejected', 'patients.timeline.titles.budgetRejectedNumbered')
      break
    case 'budget.expired':
      title = numbered('budget_number', 'patients.timeline.titles.budgetExpired', 'patients.timeline.titles.budgetExpiredNumbered')
      break
    case 'budget.renegotiated':
      title = t('patients.timeline.titles.budgetRenegotiated')
      break
    case 'budget.viewed':
      title = t('patients.timeline.titles.budgetViewed')
      break
    case 'budget.reminder_sent':
      if (has('milestone_days')) {
        const days = str(data.milestone_days)
        title = days
          ? t('patients.timeline.titles.reminderSentDays', { days })
          : t('patients.timeline.titles.reminderSent')
      }
      break
    case 'invoice.issued':
      title = numbered('invoice_number', 'patients.timeline.titles.invoiceIssued', 'patients.timeline.titles.invoiceIssuedNumbered')
      break
    case 'invoice.paid':
      title = numbered('invoice_number', 'patients.timeline.titles.invoicePaid', 'patients.timeline.titles.invoicePaidNumbered')
      break

    case 'notification.sent':
    case 'notification.failed':
      if (has('subject')) {
        const channel = data.channel === 'email'
          ? t('patients.timeline.titles.channels.email')
          : data.channel === 'whatsapp'
            ? t('patients.timeline.titles.channels.whatsapp')
            : t('patients.timeline.titles.channels.other')
        const subject = str(data.subject) ?? str(data.template_key) ?? t('patients.timeline.titles.defaultSubject')
        title = entry.event_type === 'notification.sent'
          ? t('patients.timeline.titles.messageSent', { channel, subject })
          : t('patients.timeline.titles.messageFailed', { channel, subject })
      }
      break
    case 'notification.reply_received':
      title = t('patients.timeline.titles.replyReceived')
      break

    case 'document.uploaded':
      if (has('document_title')) {
        title = t('patients.timeline.titles.documentUploaded', {
          title: str(data.document_title) ?? t('patients.timeline.titles.defaultDocument')
        })
      }
      break
    case 'media.photo_uploaded':
      if (has('document_title')) {
        const name = str(data.document_title) ?? t('patients.timeline.titles.defaultPhoto')
        title = data.media_kind === 'xray'
          ? t('patients.timeline.titles.xrayUploaded', { title: name })
          : t('patients.timeline.titles.photoUploaded', { title: name })
      }
      break
    case 'media.pair_created':
      title = t('patients.timeline.titles.pairCreated')
      break

    case 'agenda.visit_note_updated':
      title = t('patients.timeline.titles.visitNote')
      break
    case 'prescription.issued':
      title = t('patients.timeline.titles.prescriptionIssued')
      break
    case 'prescription.cancelled':
      title = t('patients.timeline.titles.prescriptionCancelled')
      break
    case 'imaging.study_indexed':
      title = t('patients.timeline.titles.imagingStudy')
      break
    case 'orthodontics.case_created':
      title = t('patients.timeline.titles.orthoCaseCreated')
      break
    case 'orthodontics.case_status_changed':
      title = t('patients.timeline.titles.orthoStatusChanged')
      break
    case 'orthodontics.control_registered':
      title = t('patients.timeline.titles.orthoControl')
      break

    default:
      if (entry.event_type.startsWith('clinical_notes.') && has('note_type')) {
        const noteType = str(data.note_type)
        const note = noteType === 'administrative'
          ? t('patients.timeline.titles.notes.administrative')
          : noteType === 'diagnosis'
            ? t('patients.timeline.titles.notes.diagnosis')
            : noteType === 'treatment'
              ? t('patients.timeline.titles.notes.treatment')
              : noteType === 'treatment_plan'
                ? t('patients.timeline.titles.notes.treatment_plan')
                : t('patients.timeline.titles.notes.generic')
        const tooth = str(data.tooth_number)
        title = noteType === 'diagnosis' && tooth
          ? t('patients.timeline.titles.notes.withTooth', { note, tooth })
          : note
      }
  }

  return title ?? entry.title
}
