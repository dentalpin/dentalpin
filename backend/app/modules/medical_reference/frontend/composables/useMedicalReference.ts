interface ApiResponse<T> { data: T }

export type ReferenceKind = 'allergies' | 'medications' | 'diseases' | 'surgeries'

export interface ReferenceItem {
  id: string
  name: string
  is_active: boolean
  is_apci?: boolean // only present for 'diseases'
}

export interface ReferenceInteraction {
  id: string
  medication_a_id: string
  medication_a_name: string
  medication_b_id: string
  medication_b_name: string
  risk_note: string
  is_active: boolean
}

export interface ReferenceContraindication {
  id: string
  disease_id: string
  disease_name: string
  medication_id: string
  medication_name: string
  risk_note: string
  is_active: boolean
}

export interface PatientFlag {
  type: 'interaction' | 'contraindication'
  risk_note: string
  involved: string[]
}

export function useMedicalReference() {
  const api = useApi()
  const { t } = useI18n()
  const toast = useToast()

  async function search(
    kind: ReferenceKind,
    query: string,
    includeInactive = false,
    limit?: number
  ): Promise<ReferenceItem[]> {
    try {
      const qs = new URLSearchParams()
      if (query) qs.set('q', query)
      if (includeInactive) qs.set('include_inactive', 'true')
      if (limit) qs.set('limit', String(limit))
      const suffix = qs.toString() ? `?${qs.toString()}` : ''
      const res = await api.get<ApiResponse<ReferenceItem[]>>(
        `/api/v1/medical_reference/${kind}${suffix}`
      )
      return res.data || []
    } catch (e) {
      console.error(`Failed to search medical_reference/${kind}:`, e)
      return []
    }
  }

  async function create(kind: ReferenceKind, data: { name: string, is_apci?: boolean }): Promise<ReferenceItem | null> {
    try {
      const res = await api.post<ApiResponse<ReferenceItem>>(`/api/v1/medical_reference/${kind}`, data)
      toast.add({ title: t('common.success'), description: t('medicalReference.addSuccess'), color: 'success' })
      return res.data
    } catch (e: any) {
      toast.add({
        title: t('common.error'),
        description: e?.data?.detail || t('medicalReference.addError'),
        color: 'error'
      })
      console.error(`Failed to create medical_reference/${kind} item:`, e)
      return null
    }
  }

  async function update(
    kind: ReferenceKind,
    id: string,
    data: { name?: string, is_apci?: boolean, is_active?: boolean }
  ): Promise<ReferenceItem | null> {
    try {
      const res = await api.put<ApiResponse<ReferenceItem>>(`/api/v1/medical_reference/${kind}/${id}`, data)
      return res.data
    } catch (e) {
      toast.add({ title: t('common.error'), description: t('medicalReference.updateError'), color: 'error' })
      console.error(`Failed to update medical_reference/${kind} item:`, e)
      return null
    }
  }

  async function deactivate(kind: ReferenceKind, id: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/medical_reference/${kind}/${id}`)
      return true
    } catch (e) {
      toast.add({ title: t('common.error'), description: t('medicalReference.deactivateError'), color: 'error' })
      console.error(`Failed to deactivate medical_reference/${kind} item:`, e)
      return false
    }
  }

  // --- Interactions ---------------------------------------------------------

  async function listInteractions(includeInactive = false): Promise<ReferenceInteraction[]> {
    try {
      const suffix = includeInactive ? '?include_inactive=true' : ''
      const res = await api.get<ApiResponse<ReferenceInteraction[]>>(
        `/api/v1/medical_reference/interactions${suffix}`
      )
      return res.data || []
    } catch (e) {
      console.error('Failed to list interactions:', e)
      return []
    }
  }

  async function createInteraction(data: {
    medication_a_id: string
    medication_b_id: string
    risk_note: string
  }): Promise<ReferenceInteraction | null> {
    try {
      const res = await api.post<ApiResponse<ReferenceInteraction>>(
        '/api/v1/medical_reference/interactions',
        data
      )
      toast.add({ title: t('common.success'), description: t('medicalReference.addSuccess'), color: 'success' })
      return res.data
    } catch (e: any) {
      toast.add({
        title: t('common.error'),
        description: e?.data?.detail || t('medicalReference.addError'),
        color: 'error'
      })
      console.error('Failed to create interaction:', e)
      return null
    }
  }

  async function deactivateInteraction(id: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/medical_reference/interactions/${id}`)
      return true
    } catch (e) {
      toast.add({ title: t('common.error'), description: t('medicalReference.deactivateError'), color: 'error' })
      console.error('Failed to deactivate interaction:', e)
      return false
    }
  }

  // --- Contraindications ---------------------------------------------------

  async function listContraindications(includeInactive = false): Promise<ReferenceContraindication[]> {
    try {
      const suffix = includeInactive ? '?include_inactive=true' : ''
      const res = await api.get<ApiResponse<ReferenceContraindication[]>>(
        `/api/v1/medical_reference/contraindications${suffix}`
      )
      return res.data || []
    } catch (e) {
      console.error('Failed to list contraindications:', e)
      return []
    }
  }

  async function createContraindication(data: {
    disease_id: string
    medication_id: string
    risk_note: string
  }): Promise<ReferenceContraindication | null> {
    try {
      const res = await api.post<ApiResponse<ReferenceContraindication>>(
        '/api/v1/medical_reference/contraindications',
        data
      )
      toast.add({ title: t('common.success'), description: t('medicalReference.addSuccess'), color: 'success' })
      return res.data
    } catch (e: any) {
      toast.add({
        title: t('common.error'),
        description: e?.data?.detail || t('medicalReference.addError'),
        color: 'error'
      })
      console.error('Failed to create contraindication:', e)
      return null
    }
  }

  async function deactivateContraindication(id: string): Promise<boolean> {
    try {
      await api.del(`/api/v1/medical_reference/contraindications/${id}`)
      return true
    } catch (e) {
      toast.add({ title: t('common.error'), description: t('medicalReference.deactivateError'), color: 'error' })
      console.error('Failed to deactivate contraindication:', e)
      return false
    }
  }

  // --- Active per-patient flags ---------------------------------------------

  async function fetchPatientFlags(patientId: string): Promise<PatientFlag[]> {
    try {
      const res = await api.get<ApiResponse<PatientFlag[]>>(
        `/api/v1/medical_reference/patients/${patientId}/flags`
      )
      return res.data || []
    } catch (e) {
      console.error('Failed to fetch patient flags:', e)
      return []
    }
  }

  return {
    search,
    create,
    update,
    deactivate,
    listInteractions,
    createInteraction,
    deactivateInteraction,
    listContraindications,
    createContraindication,
    deactivateContraindication,
    fetchPatientFlags
  }
}
