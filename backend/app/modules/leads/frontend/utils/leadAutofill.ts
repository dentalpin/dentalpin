/**
 * Pure helpers behind the convert drawer.
 *
 * Kept out of the component on purpose: they are the one place where the
 * lead -> patient mapping is decided, so they can be unit-tested without
 * mounting a USlideover (see frontend/tests/leads/leadAutofill.test.ts).
 */

export interface LeadNameParts {
  first_name: string
  last_name: string
}

/**
 * Split a single full name at the **first** whitespace.
 *
 * "Marta Ruiz" -> Marta / Ruiz. "Marta" -> Marta / "" (the form requires
 * a last name, so the user completes it). "Marta de la Fuente" ->
 * Marta / de la Fuente. It is a heuristic: the drawer keeps both fields
 * editable and nothing is written until the user confirms.
 */
export function splitFullName(fullName: string | null | undefined): LeadNameParts {
  const trimmed = (fullName ?? '').trim().replace(/\s+/g, ' ')
  if (!trimmed) return { first_name: '', last_name: '' }
  const boundary = trimmed.indexOf(' ')
  if (boundary === -1) return { first_name: trimmed, last_name: '' }
  return {
    first_name: trimmed.slice(0, boundary),
    last_name: trimmed.slice(boundary + 1).trim()
  }
}

/**
 * Trailing-9-digits comparison key — the frontend twin of the backend's
 * `matching.phone_key`. Used only for the "a patient with this phone
 * already exists" warning, so a drift here shows a warning that is
 * slightly wrong, never a wrong write.
 */
export function phoneKey(value: string | null | undefined): string {
  const digits = (value ?? '').replace(/\D/g, '')
  return digits.length >= 9 ? digits.slice(-9) : digits
}

export function phonesMatch(a: string | null | undefined, b: string | null | undefined): boolean {
  const key = phoneKey(a)
  return key.length > 0 && key === phoneKey(b)
}
