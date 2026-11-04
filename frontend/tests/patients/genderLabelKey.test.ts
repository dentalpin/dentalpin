import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { genderLabelKey } from '../../../backend/app/modules/patients/frontend/utils/genderLabelKey'

function lookup(messages: unknown, key: string): unknown {
  return key.split('.').reduce<unknown>(
    (node, part) => (node as Record<string, unknown> | undefined)?.[part],
    messages
  )
}

describe('genderLabelKey', () => {
  const en = JSON.parse(readFileSync(resolve(__dirname, '../../i18n/locales/en.json'), 'utf8'))

  it.each(['male', 'female', 'other', 'prefer_not_say'])('%s maps to a key that exists', (gender) => {
    const key = genderLabelKey(gender)
    expect(key).not.toBeNull()
    expect(typeof lookup(en, key!)).toBe('string')
  })

  it.each([null, undefined, '', 'made_up'])('%s shows nothing', (gender) => {
    expect(genderLabelKey(gender)).toBeNull()
  })
})
