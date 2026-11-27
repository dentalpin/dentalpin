/**
 * Which cabinets the agenda offers (#1237). An inactive cabinet can't take
 * new appointments, so pickers and agenda resources leave it out, except
 * where an existing appointment still sits in it: that one must stay
 * visible and editable.
 */
interface CabinetLike {
  name: string
  is_active?: boolean
}

const isActive = (cabinet: CabinetLike) => cabinet.is_active !== false

/** Active cabinets plus inactive ones that hold one of the loaded appointments. */
export function agendaCabinets<C extends CabinetLike>(
  cabinets: readonly C[],
  appointments: readonly { cabinet: string | null }[]
): C[] {
  const used = new Set(appointments.map(a => a.cabinet).filter(Boolean))
  return cabinets.filter(c => isActive(c) || used.has(c.name))
}

/** Cabinets a booking can pick: the active ones, plus the one it already has. */
export function pickableCabinets<C extends CabinetLike>(
  cabinets: readonly C[],
  current?: string | null
): C[] {
  return cabinets.filter(c => isActive(c) || c.name === current)
}
