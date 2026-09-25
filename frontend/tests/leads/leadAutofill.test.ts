// @vitest-environment node
import { describe, expect, it } from 'vitest'
import {
  phoneKey,
  phonesMatch,
  splitFullName
} from '#module-layers/leads/frontend/utils/leadAutofill'

/**
 * The one piece of guessing in the convert flow: how the enquiry's single
 * name field becomes first_name / last_name, plus the trailing-9-digits
 * phone rule the duplicate warning shares with the backend. Pure functions,
 * tested here instead of through a mounted USlideover.
 */
describe('splitFullName', () => {
  it('splits at the first whitespace', () => {
    expect(splitFullName('Marta Ruiz')).toEqual({ first_name: 'Marta', last_name: 'Ruiz' })
  })

  it('keeps a compound surname together', () => {
    expect(splitFullName('Marta de la Fuente')).toEqual({
      first_name: 'Marta',
      last_name: 'de la Fuente'
    })
  })

  it('leaves the last name empty for a single token', () => {
    expect(splitFullName('Marta')).toEqual({ first_name: 'Marta', last_name: '' })
  })

  it('collapses runs of whitespace and handles empties', () => {
    expect(splitFullName('  Ana   Maria  Gil ')).toEqual({
      first_name: 'Ana',
      last_name: 'Maria Gil'
    })
    expect(splitFullName('')).toEqual({ first_name: '', last_name: '' })
    expect(splitFullName(null)).toEqual({ first_name: '', last_name: '' })
  })
})

describe('phoneKey / phonesMatch', () => {
  it('compares the trailing 9 digits', () => {
    expect(phoneKey('+34 600 111 222')).toBe('600111222')
    expect(phonesMatch('600 111 222', '600111222')).toBe(true)
    expect(phonesMatch('+34 600 111 222', '600111222')).toBe(true)
    expect(phonesMatch('600111223', '600111222')).toBe(false)
  })

  it('never matches on an empty number', () => {
    expect(phonesMatch(null, '600111222')).toBe(false)
    expect(phonesMatch('', '')).toBe(false)
  })
})
