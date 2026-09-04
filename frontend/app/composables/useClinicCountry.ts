/**
 * Server-side clinic country (ISO alpha-2) for method gating (#365).
 *
 * Lives in the host (not the payments layer) because the shared
 * ``CollectAmountModal`` needs the same gate and a host component cannot
 * import from a module layer; layers auto-import it by name as before.
 *
 * Read the same way ``india_gst``'s slot gate does — top-level
 * ``clinic.country`` or the legacy ``settings.country`` — never a
 * client-editable field. The shared ``Clinic`` type doesn't surface the
 * top-level key, hence the local widening.
 */
type ClinicWithCountry = {
  country?: string | null
  settings?: { country?: string | null } | null
} | null

export function useClinicCountry() {
  const { currentClinic } = useClinic()
  return computed(() => {
    const c = currentClinic.value as ClinicWithCountry
    return c?.country ?? c?.settings?.country ?? null
  })
}
