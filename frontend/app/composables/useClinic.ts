import type { Cabinet, CabinetCreate, CabinetUpdate, Clinic, ClinicMembership, ClinicUpdate, PaginatedResponse, ApiResponse } from '~/types'

/**
 * Context-free access to the clinic state (only ``useState``). Use from
 * code that may run outside a component setup — e.g. getting-started
 * rule predicates evaluated inside computeds/watchers — where
 * ``useClinic()`` (``useI18n``, ``useToast``) would throw.
 */
export function useClinicState() {
  return {
    currentClinic: useState<Clinic | null>('clinic:current', () => null)
  }
}

export function useClinic() {
  const api = useApi()
  const auth = useAuth()
  const toast = useToast()
  const { t } = useI18n()

  // State
  const { currentClinic } = useClinicState()
  const membership = useState<ClinicMembership | null>('clinic:membership', () => null)
  const isLoading = useState<boolean>('clinic:loading', () => false)

  // Computed
  const clinicName = computed(() => currentClinic.value?.name || '')
  const cabinets = computed(() => currentClinic.value?.cabinets || [])
  const slotDuration = computed(() => currentClinic.value?.settings?.slot_duration_min || 15)
  // Clinic-wide default from the billing settings registry (#755); the
  // registry default is 30 when unset. ?? not ||: 0 is a valid term
  // (paid up front).
  const defaultPaymentTermDays = computed(
    () => currentClinic.value?.settings?.billing?.default_payment_term_days ?? 30
  )

  // Actions
  async function fetchClinic(): Promise<void> {
    if (!auth.isAuthenticated.value) {
      return
    }

    isLoading.value = true
    try {
      // Get user's clinics (for MVP, we just use the first one)
      const response = await api.get<PaginatedResponse<Clinic>>('/api/v1/auth/clinics')
      if (response.data.length > 0) {
        currentClinic.value = response.data[0] ?? null
      }
    } catch (error) {
      console.error('Failed to fetch clinic:', error)
    } finally {
      isLoading.value = false
    }
  }

  async function updateClinic(data: ClinicUpdate): Promise<Clinic | null> {
    try {
      // The catch below toasts the failure itself.
      const response = await api.put<ApiResponse<Clinic>>('/api/v1/auth/clinics', data, { errorToast: false })
      currentClinic.value = response.data
      toast.add({
        title: t('common.success'),
        description: t('settings.clinicUpdated'),
        color: 'success'
      })
      return response.data
    } catch (e: unknown) {
      toast.add({
        title: t('common.error'),
        description: t('settings.clinicUpdateError'),
        color: 'error'
      })
      console.error('Failed to update clinic:', e)
      return null
    }
  }

  // Merge a partial settings object into the local Clinic state (after a
  // settings PATCH) without re-fetching the whole clinic payload.
  function patchSettings(partial: Partial<Clinic['settings']>): void {
    const clinic = currentClinic.value
    if (!clinic) return
    currentClinic.value = { ...clinic, settings: { ...(clinic.settings ?? {}), ...partial } }
  }

  // Mutate the cabinets array on the local Clinic state without re-fetching
  // the entire clinic payload.
  function patchCabinets(mutate: (list: Cabinet[]) => Cabinet[]): Cabinet[] | null {
    const clinic = currentClinic.value
    if (!clinic) return null
    const snapshot = clinic.cabinets ?? []
    currentClinic.value = { ...clinic, cabinets: mutate(snapshot.slice()) }
    return snapshot
  }

  async function createCabinet(data: CabinetCreate): Promise<Cabinet | null> {
    try {
      const response = await api.post<ApiResponse<Cabinet>>('/api/v1/agenda/cabinets', data, { errorToast: false })
      patchCabinets(list => [...list, response.data])
      toast.add({
        title: t('common.success'),
        description: t('cabinet.toast.created'),
        color: 'success'
      })
      return response.data
    } catch (e: unknown) {
      const fetchError = e as { statusCode?: number }
      const description = fetchError.statusCode === 409
        ? t('cabinet.toast.duplicateName')
        : t('cabinet.toast.createFailed')
      toast.add({ title: t('common.error'), description, color: 'error' })
      console.error('Failed to create cabinet:', e)
      return null
    }
  }

  async function updateCabinet(cabinetId: string, data: CabinetUpdate): Promise<Cabinet | null> {
    const rollback = patchCabinets(list =>
      list.map(c => c.id === cabinetId ? { ...c, ...data } as Cabinet : c)
    )
    try {
      const response = await api.put<ApiResponse<Cabinet>>(`/api/v1/agenda/cabinets/${cabinetId}`, data, { errorToast: false })
      patchCabinets(list => list.map(c => c.id === cabinetId ? response.data : c))
      toast.add({
        title: t('common.success'),
        description: t('cabinet.toast.updated'),
        color: 'success'
      })
      return response.data
    } catch (e: unknown) {
      if (rollback) patchCabinets(() => rollback)
      const fetchError = e as { statusCode?: number }
      const key = fetchError.statusCode === 409
        ? 'cabinet.toast.duplicateName'
        : fetchError.statusCode === 404
          ? 'cabinet.toast.notFound'
          : 'cabinet.toast.updateFailed'
      toast.add({ title: t('common.error'), description: t(key), color: 'error' })
      console.error('Failed to update cabinet:', e)
      return null
    }
  }

  async function deleteCabinet(cabinetId: string): Promise<boolean> {
    const rollback = patchCabinets(list => list.filter(c => c.id !== cabinetId))
    try {
      await api.del(`/api/v1/agenda/cabinets/${cabinetId}`, { errorToast: false })
      toast.add({
        title: t('common.success'),
        description: t('cabinet.toast.deleted'),
        color: 'success'
      })
      return true
    } catch (e: unknown) {
      if (rollback) patchCabinets(() => rollback)
      const fetchError = e as { statusCode?: number }
      const key = fetchError.statusCode === 404
        ? 'cabinet.toast.notFound'
        : 'cabinet.toast.deleteFailed'
      toast.add({ title: t('common.error'), description: t(key), color: 'error' })
      console.error('Failed to delete cabinet:', e)
      return false
    }
  }

  // Initialize clinic when auth state changes
  watch(() => auth.isAuthenticated.value, async (isAuth) => {
    if (isAuth && !currentClinic.value) {
      await fetchClinic()
    } else if (!isAuth) {
      currentClinic.value = null
      membership.value = null
    }
  }, { immediate: true })

  return {
    currentClinic: readonly(currentClinic),
    membership: readonly(membership),
    isLoading: readonly(isLoading),
    clinicName,
    cabinets,
    slotDuration,
    defaultPaymentTermDays,
    fetchClinic,
    updateClinic,
    patchSettings,
    createCabinet,
    updateCabinet,
    deleteCabinet
  }
}
