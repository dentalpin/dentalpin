import { describe, expect, it } from 'vitest'
import { getOcclusalPath } from '../../module_layers/odontogram/frontend/components/odontogram/ToothSVGPaths'

/** Count vertices in an M/L/.../Z polygon path (coordinate pairs). */
function vertexCount(path: string): number {
  return (path.match(/-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?/g) ?? []).length
}

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

  it('builds each surface as a closed quad (4 vertices)', () => {
    for (const tooth of [11, 13, 14, 16]) {
      const surfaces = getOcclusalPath(tooth).surfaces
      for (const [name, path] of Object.entries(surfaces)) {
        expect(vertexCount(path), `${tooth} surface ${name}`).toBe(4)
        expect(path.trim().endsWith('Z')).toBe(true)
      }
    }
  })
})
