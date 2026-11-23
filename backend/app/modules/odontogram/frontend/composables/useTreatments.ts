/**
 * useTreatments - CRUD for Treatment (header + teeth[] model)
 *
 * Single unified endpoint `/patients/{id}/treatments`. Scope is derived from
 * tooth count for tooth/multi_tooth cases; global_mouth and global_arch must
 * be passed explicitly.
 */

import type {
  ApiResponse,
  Arch,
  PaginatedResponse,
  ToothRecordWithTreatments,
  Treatment,
  TreatmentCreate,
  TreatmentStatus,
  TreatmentUpdate
} from '~~/app/types'

// ---------------------------------------------------------------------------
// Backend <-> frontend status mapping.
// Backend: 'planned' | 'performed'. Frontend: 'planned' | 'existing' (clinical UI).
// ---------------------------------------------------------------------------

function toBackendStatus(v: TreatmentStatus | undefined): 'planned' | 'performed' | undefined {
  if (v === 'existing') return 'performed'
  return v
}

function fromBackendStatus(v: string | undefined | null): TreatmentStatus {
  return v === 'performed' ? 'existing' : 'planned'
}

export function normalizeTreatment<T extends { status: string }>(treatment: T): T {
  return { ...treatment, status: fromBackendStatus(treatment.status) }
}

// The list endpoint's `le=` cap.
const TREATMENTS_PAGE_SIZE = 100

export function useTreatments() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  // ============================================================================
  // State
  // ============================================================================

  const treatments = ref<Treatment[]>([])
  const loading = ref(false)

  // ============================================================================
  // Helpers
  // ============================================================================

  /** Treatments whose teeth[] includes the given tooth. */
  function getToothTreatments(toothNumber: number): Treatment[] {
    return treatments.value.filter(t =>
      t.teeth.some(tt => tt.tooth_number === toothNumber)
    )
  }

  function getTreatmentsByStatus(status: TreatmentStatus): Treatment[] {
    return treatments.value.filter(t => t.status === status)
  }

  function updateLocalTreatment(updated: Treatment): void {
    const index = treatments.value.findIndex(t => t.id === updated.id)
    if (index >= 0) {
      treatments.value[index] = updated
    }
  }

  function removeLocalTreatment(treatmentId: string): void {
    treatments.value = treatments.value.filter(t => t.id !== treatmentId)
  }

  // ============================================================================
  // API
  // ============================================================================

  async function fetchTreatments(
    patientId: string,
    filters?: { status?: TreatmentStatus, tooth_number?: number, clinical_type?: string }
  ): Promise<void> {
    loading.value = true
    try {
      const params = new URLSearchParams()
      if (filters?.status) params.append('status', filters.status)
      if (filters?.tooth_number) params.append('tooth_number', String(filters.tooth_number))
      if (filters?.clinical_type) params.append('clinical_type', filters.clinical_type)
      params.set('page_size', String(TREATMENTS_PAGE_SIZE))

      // The chart draws every tooth from this list, so it must be complete:
      // the endpoint pages (newest first, default 50), and a long-standing
      // patient's oldest rows — the initial charting — would fall off the
      // chart. Walk every page.
      const rows: Treatment[] = []
      for (let page = 1; ; page++) {
        params.set('page', String(page))
        const response = await api.get<PaginatedResponse<Treatment>>(
          `/api/v1/odontogram/patients/${patientId}/treatments?${params.toString()}`
        )
        rows.push(...response.data)
        if (response.data.length < TREATMENTS_PAGE_SIZE || rows.length >= response.total) break
      }
      treatments.value = rows.map(normalizeTreatment)
    } catch (err) {
      console.error('Error fetching treatments:', err)
    } finally {
      loading.value = false
    }
  }

  /** Unified create: single-tooth, bridge or uniform multi-tooth. */
  async function createTreatment(
    patientId: string,
    payload: TreatmentCreate
  ): Promise<Treatment | null> {
    try {
      const body = {
        ...payload,
        status: toBackendStatus(payload.status)
      }
      const response = await api.post<ApiResponse<Treatment>>(
        `/api/v1/odontogram/patients/${patientId}/treatments`,
        body,
        { errorToast: false }
      )
      const normalized = normalizeTreatment(response.data)
      treatments.value.push(normalized)
      return normalized
    } catch (err) {
      toast.add({
        title: t('common.error'),
        description: t('odontogram.messages.error'),
        color: 'error'
      })
      console.error('Error creating treatment:', err)
      return null
    }
  }

  async function updateTreatment(
    treatmentId: string,
    data: TreatmentUpdate
  ): Promise<Treatment | null> {
    try {
      const body = { ...data, status: toBackendStatus(data.status) }
      const response = await api.put<ApiResponse<Treatment>>(
        `/api/v1/odontogram/treatments/${treatmentId}`,
        body as Record<string, unknown>,
        { errorToast: false }
      )
      const normalized = normalizeTreatment(response.data)
      updateLocalTreatment(normalized)
      toast.add({ title: t('odontogram.messages.updated'), color: 'success' })
      return normalized
    } catch (err) {
      toast.add({
        title: t('common.error'),
        description: t('odontogram.messages.error'),
        color: 'error'
      })
      console.error('Error updating treatment:', err)
      return null
    }
  }

  async function deleteTreatment(treatmentId: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/odontogram/treatments/${treatmentId}`, { errorToast: false })
      removeLocalTreatment(treatmentId)
      toast.add({ title: t('odontogram.treatments.treatmentDeleted'), color: 'success' })
      return true
    } catch (err) {
      toast.add({
        title: t('common.error'),
        description: t('odontogram.messages.error'),
        color: 'error'
      })
      console.error('Error deleting treatment:', err)
      return false
    }
  }

  async function performTreatment(
    treatmentId: string,
    notes?: string
  ): Promise<Treatment | null> {
    try {
      const response = await api.patch<ApiResponse<Treatment>>(
        `/api/v1/odontogram/treatments/${treatmentId}/perform`,
        { notes } as Record<string, unknown>,
        { errorToast: false }
      )
      const normalized = normalizeTreatment(response.data)
      updateLocalTreatment(normalized)
      toast.add({ title: t('odontogram.treatments.treatmentPerformed'), color: 'success' })
      return normalized
    } catch (err) {
      toast.add({
        title: t('common.error'),
        description: t('odontogram.messages.error'),
        color: 'error'
      })
      console.error('Error performing treatment:', err)
      return null
    }
  }

  /** Create a global treatment (no teeth). `arch` required only for global_arch. */
  async function createGlobalTreatment(
    patientId: string,
    params: {
      catalogItemId: string
      scope: 'global_mouth' | 'global_arch'
      arch?: Arch
      status?: TreatmentStatus
      notes?: string
    }
  ): Promise<Treatment | null> {
    if (params.scope === 'global_arch' && !params.arch) {
      console.error('createGlobalTreatment: arch is required for global_arch')
      return null
    }
    return createTreatment(patientId, {
      catalog_item_id: params.catalogItemId,
      scope: params.scope,
      arch: params.arch,
      status: params.status ?? 'planned',
      notes: params.notes
    })
  }

  async function fetchToothWithTreatments(
    patientId: string,
    toothNumber: number
  ): Promise<ToothRecordWithTreatments | null> {
    try {
      const response = await api.get<ApiResponse<ToothRecordWithTreatments>>(
        `/api/v1/odontogram/patients/${patientId}/teeth/${toothNumber}/full`
      )
      return {
        ...response.data,
        treatments: (response.data.treatments || []).map(normalizeTreatment)
      }
    } catch (err) {
      console.error('Error fetching tooth with treatments:', err)
      return null
    }
  }

  function reset(): void {
    treatments.value = []
  }

  return {
    // State
    treatments,
    loading,
    // Helpers
    getToothTreatments,
    getTreatmentsByStatus,
    // API
    fetchTreatments,
    createTreatment,
    createGlobalTreatment,
    updateTreatment,
    deleteTreatment,
    performTreatment,
    fetchToothWithTreatments,
    reset
  }
}
