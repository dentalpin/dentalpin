/**
 * Field validation for the leads forms.
 *
 * These are the **client-side guards**: they stop an obviously wrong value
 * from being sent and tell the user in their own language what is wrong.
 * The server stays the authority — pydantic validates the same payload and
 * answers 422, which the forms surface as a toast — but a round trip for a
 * typo'd email is bad manners and, on the convert drawer, would create
 * nothing while looking like it did.
 *
 * The rules deliberately mirror what the backend will accept, field by
 * field (see schemas.py / patients.schemas), so a value that passes here
 * is not rejected there:
 *   - email: single @, no spaces/leading-dot/double-dot, dot in the domain,
 *     2+ char TLD, ≤254 chars — pydantic's EmailStr rejects @a@b, a@b and
 *     a..b@example.com, and so must we.
 *   - phone: allowed punctuation only, ≥6 digits, within the column width
 *     (32 for the lead, 20 for the patient record).
 *   - date_of_birth: a real date, not in the future, not older than 120y.
 *
 * Pure functions returning a message key, so the components stay thin and
 * the rules are unit-tested without mounting a form.
 */

export type ValidationKey = 'required' | 'email' | 'phone' | 'dateOfBirth'

const PHONE_ALLOWED = /^[0-9+()\-./\s]+$/
const EMAIL_LOCAL = /^[A-Za-z0-9!#$%&'*+/=?^_\u0060{|}~.-]+$/
const EMAIL_DOMAIN = /^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$/

function required(value: string | null | undefined): boolean {
  return Boolean(value && value.trim())
}

/**
 * A pragmatic email check: strict about what the backend rejects,
 * tolerant about the exotic-but-legal (quoted local parts are not worth
 * the complexity here — the server would accept them, this refuses them,
 * and that is the safe direction for a typo guard).
 */
export function isValidEmail(value: string | null | undefined): boolean {
  const candidate = (value ?? '').trim()
  if (!candidate || candidate.length > 254 || /\s/.test(candidate)) return false
  const at = candidate.indexOf('@')
  if (at <= 0 || at !== candidate.lastIndexOf('@')) return false
  const local = candidate.slice(0, at)
  const domain = candidate.slice(at + 1)
  if (!local || local.length > 64) return false
  if (local.startsWith('.') || local.endsWith('.') || local.includes('..')) return false
  if (!EMAIL_LOCAL.test(local) || !EMAIL_DOMAIN.test(domain)) return false
  const tld = domain.slice(domain.lastIndexOf('.') + 1)
  return tld.length >= 2
}

export function isValidPhone(
  value: string | null | undefined,
  options: { required?: boolean, maxLength?: number } = {}
): boolean {
  const { required: isRequired = false, maxLength = 32 } = options
  const candidate = (value ?? '').trim()
  if (!candidate) return !isRequired
  if (candidate.length > maxLength) return false
  if (!PHONE_ALLOWED.test(candidate)) return false
  const digits = candidate.replace(/\D/g, '')
  return digits.length >= 6
}

export function isValidDateOfBirth(value: string | null | undefined): boolean {
  const candidate = (value ?? '').trim()
  if (!candidate) return true // optional everywhere it is used
  const parsed = new Date(`${candidate}T00:00:00`)
  if (Number.isNaN(parsed.getTime())) return false
  const endOfToday = new Date()
  endOfToday.setHours(23, 59, 59, 999)
  const earliest = new Date()
  earliest.setFullYear(earliest.getFullYear() - 120)
  earliest.setHours(0, 0, 0, 0)
  return parsed <= endOfToday && parsed >= earliest
}

export interface LeadFormValues {
  full_name: string
  phone: string
  email: string
  motive: string
  description?: string
  availability?: string
}

export type LeadFormErrors = Partial<Record<keyof LeadFormValues, ValidationKey>>

/** Manual create / edit. Mirrors LeadCreate in schemas.py. */
export function validateLeadForm(values: LeadFormValues): LeadFormErrors {
  const errors: LeadFormErrors = {}
  if (!required(values.full_name)) errors.full_name = 'required'
  if (!isValidPhone(values.phone, { required: true, maxLength: 32 })) errors.phone = 'phone'
  if (required(values.email) && !isValidEmail(values.email)) errors.email = 'email'
  if (!required(values.motive)) errors.motive = 'required'
  return errors
}

export interface PatientFormValues {
  first_name: string
  last_name: string
  phone: string
  email: string
  date_of_birth: string
}

export type PatientFormErrors = Partial<Record<keyof PatientFormValues, ValidationKey>>

/** The convert drawer. Mirrors LeadConvertRequest + the patients columns
 *  (phone is String(20) there, which is where the 20 comes from). */
export function validatePatientForm(values: PatientFormValues): PatientFormErrors {
  const errors: PatientFormErrors = {}
  if (!required(values.first_name)) errors.first_name = 'required'
  if (!required(values.last_name)) errors.last_name = 'required'
  if (!isValidPhone(values.phone, { required: false, maxLength: 20 })) errors.phone = 'phone'
  if (required(values.email) && !isValidEmail(values.email)) errors.email = 'email'
  if (!isValidDateOfBirth(values.date_of_birth)) errors.date_of_birth = 'dateOfBirth'
  return errors
}

export function hasErrors(errors: Record<string, ValidationKey | undefined>): boolean {
  return Object.values(errors).some(Boolean)
}
