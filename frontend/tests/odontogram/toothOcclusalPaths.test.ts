import { describe, expect, it } from 'vitest'
import { getOcclusalPath } from '../../module_layers/odontogram/frontend/components/odontogram/ToothSVGPaths'

describe('getOcclusalPath', () => {
  it('returns category-specific outlines for incisor, canine, premolar, and molar', () => {
    const incisor = getOcclusalPath(11).outline
    const canine = getOcclusalPath(13).outline
    const premolar = getOcclusalPath(14).outline
    const molar = getOcclusalPath(16).outline

    expect(incisor).not.toBe(canine)
    expect(canine).not.toBe(premolar)
    expect(premolar).not.toBe(molar)
    expect(incisor).not.toBe(molar)
  })

  it('exposes all five standard surface paths per tooth', () => {
    const surfaces = getOcclusalPath(26).surfaces
    expect(Object.keys(surfaces).sort()).toEqual(['D', 'L', 'M', 'O', 'V'])
    for (const path of Object.values(surfaces)) {
      expect(path.startsWith('M ')).toBe(true)
    }
  })
})
