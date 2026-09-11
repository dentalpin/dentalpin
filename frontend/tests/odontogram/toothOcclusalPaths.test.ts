import { describe, expect, it } from 'vitest'
import { getOcclusalPath } from '#module-layers/odontogram/frontend/components/odontogram/ToothSVGPaths'

/** Count vertices in an M/L/.../Z polygon path (coordinate pairs). */
function vertexCount(path: string): number {
  return (path.match(/-?\d+(?:\.\d+)?,-?\d+(?:\.\d+)?/g) ?? []).length
}

interface Point { x: number, y: number }

/** Sample every M/L/C/Q segment so curve extremes are included in the bounds. */
function samplePath(path: string): Point[] {
  const tokens = path.match(/[MCLQZ]|-?\d+(?:\.\d+)?/g) ?? []
  const points: Point[] = []
  let index = 0
  let command = ''
  let current: Point = { x: 0, y: 0 }
  let start: Point = current
  const number = () => Number(tokens[index++])

  while (index < tokens.length) {
    const token = tokens[index]!
    if (/^[MCLQZ]$/.test(token)) {
      command = token
      index += 1
      continue
    }
    if (command === 'M' || command === 'L') {
      current = { x: number(), y: number() }
      if (command === 'M') start = current
      points.push(current)
    } else if (command === 'C') {
      const control1 = { x: number(), y: number() }
      const control2 = { x: number(), y: number() }
      const target = { x: number(), y: number() }
      for (let step = 0; step <= 32; step++) {
        const t = step / 32
        const mt = 1 - t
        points.push({
          x: mt ** 3 * current.x + 3 * mt * mt * t * control1.x + 3 * mt * t * t * control2.x + t ** 3 * target.x,
          y: mt ** 3 * current.y + 3 * mt * mt * t * control1.y + 3 * mt * t * t * control2.y + t ** 3 * target.y
        })
      }
      current = target
    } else if (command === 'Q') {
      const control = { x: number(), y: number() }
      const target = { x: number(), y: number() }
      for (let step = 0; step <= 32; step++) {
        const t = step / 32
        const mt = 1 - t
        points.push({
          x: mt * mt * current.x + 2 * mt * t * control.x + t * t * target.x,
          y: mt * mt * current.y + 2 * mt * t * control.y + t * t * target.y
        })
      }
      current = target
    } else if (command === 'Z') {
      points.push(start)
      current = start
      index += 1
    } else {
      index += 1
    }
  }
  return points
}

function bounds(points: Point[]) {
  return {
    minX: Math.min(...points.map(p => p.x)),
    minY: Math.min(...points.map(p => p.y)),
    maxX: Math.max(...points.map(p => p.x)),
    maxY: Math.max(...points.map(p => p.y))
  }
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

  it('over-sizes the outer quad so each surface band encloses the outline bounding box', () => {
    for (const tooth of [11, 13, 14, 16]) {
      const { outline, surfaces } = getOcclusalPath(tooth)
      const outlineBounds = bounds(samplePath(outline))
      const surfaceBounds = bounds(Object.values(surfaces).flatMap(samplePath))
      // Outer corners extend past the silhouette (callers clip fills to outline),
      // so the incisal, cervical and lateral bands are fillable and clickable.
      expect(surfaceBounds.minX, `${tooth} minX`).toBeLessThanOrEqual(outlineBounds.minX)
      expect(surfaceBounds.minY, `${tooth} minY`).toBeLessThanOrEqual(outlineBounds.minY)
      expect(surfaceBounds.maxX, `${tooth} maxX`).toBeGreaterThanOrEqual(outlineBounds.maxX)
      expect(surfaceBounds.maxY, `${tooth} maxY`).toBeGreaterThanOrEqual(outlineBounds.maxY)
    }
  })
})
