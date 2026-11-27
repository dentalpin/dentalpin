import { describe, expect, it } from 'vitest'
import { agendaCabinets, pickableCabinets } from '../../../backend/app/modules/agenda/frontend/utils/activeCabinets'

/** #1237: an inactive cabinet is not offered, but its existing appointments stay reachable. */
const cabinets = [
  { name: 'Gabinete 1', is_active: true },
  { name: 'Old room', is_active: false },
  { name: 'Legacy' } // no flag sent: treated as active
]

describe('agendaCabinets', () => {
  it('leaves out an inactive cabinet with no loaded appointment', () => {
    expect(agendaCabinets(cabinets, [{ cabinet: 'Gabinete 1' }, { cabinet: null }]).map(c => c.name))
      .toEqual(['Gabinete 1', 'Legacy'])
  })

  it('keeps an inactive cabinet while it holds a loaded appointment', () => {
    expect(agendaCabinets(cabinets, [{ cabinet: 'Old room' }]).map(c => c.name))
      .toEqual(['Gabinete 1', 'Old room', 'Legacy'])
  })
})

describe('pickableCabinets', () => {
  it('offers only active cabinets for a new booking', () => {
    expect(pickableCabinets(cabinets).map(c => c.name)).toEqual(['Gabinete 1', 'Legacy'])
  })

  it('keeps the inactive cabinet an edited appointment already sits in', () => {
    expect(pickableCabinets(cabinets, 'Old room').map(c => c.name))
      .toEqual(['Gabinete 1', 'Old room', 'Legacy'])
  })
})
