// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  hasErrors,
  isValidDateOfBirth,
  isValidEmail,
  isValidPhone,
  validateLeadForm,
  validatePatientForm
} from '#module-layers/leads/frontend/utils/leadValidation'

/**
 * The client-side guards. They exist so a typo is caught before the round
 * trip (and before the convert drawer creates nothing while looking like
 * it did) — the server stays the authority, so anything accepted here must
 * also be accepted by pydantic.
 */
describe('isValidEmail', () => {
  it('accepts ordinary addresses', () => {
    for (const value of [
      'marta@example.com',
      'marta.ruiz@example.co.uk',
      'MARTA+clinica@Example.COM',
      'o\'brien@example.com',
      'a_b-c@sub.domain.example.org'
    ]) {
      expect(isValidEmail(value), value).toBe(true)
    }
  })

  it('rejects what the backend also rejects', () => {
    for (const value of [
      '',
      '   ',
      'marta',
      'marta@',
      '@example.com',
      'marta@example', // no dot in the domain — EmailStr refuses it
      'marta@example.',
      'marta@.com',
      'a..b@example.com',
      '.marta@example.com',
      'marta.@example.com',
      'marta`example.com',
      'marta @example.com',
      'marta@exa mple.com',
      'marta@example.c'
    ]) {
      expect(isValidEmail(value), value).toBe(false)
    }
  })

  it('rejects an over-long address', () => {
    expect(isValidEmail(`${'a'.repeat(60)}@${'b'.repeat(200)}.com`)).toBe(false)
  })
})

describe('isValidPhone', () => {
  it('accepts real-world formats within the column width', () => {
    for (const value of ['+34 600 111 222', '600111222', '+1 (212) 555-0001', '91-555-12-34']) {
      expect(isValidPhone(value, { required: true }), value).toBe(true)
    }
  })

  it('rejects letters and too-few digits', () => {
    for (const value of ['llámame', '600', 'abc123456', '+34 600 111 222 ext 3']) {
      expect(isValidPhone(value, { required: true }), value).toBe(false)
    }
  })

  it('respects the column width of each form', () => {
    const long = '+34 600 111 222 333 444'
    expect(isValidPhone(long, { required: true, maxLength: 32 })).toBe(true)
    // 20 chars is the patients.phone column the convert drawer writes to.
    expect(isValidPhone(long, { maxLength: 20 })).toBe(false)
  })

  it('treats empty as valid unless the field is required', () => {
    expect(isValidPhone('', { required: true })).toBe(false)
    expect(isValidPhone('', { required: false })).toBe(true)
  })
})

describe('isValidDateOfBirth', () => {
  it('accepts a plausible past date and empty', () => {
    expect(isValidDateOfBirth('1990-04-02')).toBe(true)
    expect(isValidDateOfBirth('')).toBe(true)
    expect(isValidDateOfBirth(null)).toBe(true)
  })

  it('rejects the future, the absurd and the malformed', () => {
    const nextYear = new Date()
    nextYear.setFullYear(nextYear.getFullYear() + 1)
    expect(isValidDateOfBirth(nextYear.toISOString().slice(0, 10))).toBe(false)
    expect(isValidDateOfBirth('1799-01-01')).toBe(false)
    expect(isValidDateOfBirth('not-a-date')).toBe(false)
  })
})

describe('validateLeadForm / validatePatientForm', () => {
  const lead = {
    full_name: 'Marta Ruiz',
    phone: '+34 600 111 222',
    email: 'marta@example.com',
    motive: 'Ortodoncia',
    description: '',
    availability: ''
  }

  it('passes a good lead, with an empty optional email', () => {
    expect(hasErrors(validateLeadForm(lead))).toBe(false)
    expect(hasErrors(validateLeadForm({ ...lead, email: '' }))).toBe(false)
  })

  it('names every invalid lead field', () => {
    const errors = validateLeadForm({
      full_name: '  ',
      phone: '600',
      email: 'marta@example',
      motive: ''
    })
    expect(errors).toEqual({
      full_name: 'required',
      phone: 'phone',
      email: 'email',
      motive: 'required'
    })
  })

  it('names every invalid patient field', () => {
    const errors = validatePatientForm({
      first_name: '',
      last_name: '',
      phone: 'llámame',
      email: 'marta@example',
      date_of_birth: '2999-01-01'
    })
    expect(errors).toEqual({
      first_name: 'required',
      last_name: 'required',
      phone: 'phone',
      email: 'email',
      date_of_birth: 'dateOfBirth'
    })
  })

  it('accepts a patient with no phone, email or birth date', () => {
    expect(
      hasErrors(
        validatePatientForm({
          first_name: 'Marta',
          last_name: 'Ruiz',
          phone: '',
          email: '',
          date_of_birth: ''
        })
      )
    ).toBe(false)
  })
})
