import { describe, expect, it } from 'vitest'
import { mergeLayerLocales } from '../modules/i18n-consolidate'

/**
 * The consolidated file must reproduce what @nuxtjs/i18n does with the
 * separate files: an earlier layer overrides a later one, nested
 * namespaces merge instead of replacing each other, and locales a layer
 * does not ship stay untouched.
 */
describe('mergeLayerLocales', () => {
  it('merges namespaces across layers and keeps the earlier layer on conflicts', () => {
    const merged = mergeLayerLocales([
      [{ code: 'en', data: { a: { title: 'A first', shared: 'first wins' } } }],
      [{ code: 'en', data: { a: { subtitle: 'A second', shared: 'second loses' }, b: { title: 'B' } } }]
    ])
    expect(merged.get('en')).toEqual({
      a: { title: 'A first', subtitle: 'A second', shared: 'first wins' },
      b: { title: 'B' }
    })
  })

  it('keeps locales separate and tolerates layers without a locale', () => {
    const merged = mergeLayerLocales([
      [{ code: 'en', data: { a: 'en' } }, { code: 'es', data: { a: 'es' } }],
      [{ code: 'en', data: { b: 'en' } }]
    ])
    expect(merged.get('en')).toEqual({ a: 'en', b: 'en' })
    expect(merged.get('es')).toEqual({ a: 'es' })
    expect(merged.has('fr')).toBe(false)
  })

  it('replaces scalars and arrays rather than merging into them', () => {
    const merged = mergeLayerLocales([
      [{ code: 'en', data: { list: ['x'], leaf: 'string' } }],
      [{ code: 'en', data: { list: ['y', 'z'], leaf: { nested: true } } }]
    ])
    expect(merged.get('en')).toEqual({ list: ['x'], leaf: 'string' })
  })
})
