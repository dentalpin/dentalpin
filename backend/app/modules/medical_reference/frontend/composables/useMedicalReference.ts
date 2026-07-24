interface ApiResponse<T> { data: T }

export type ReferenceKind = 'allergies' | 'medications' | 'diseases'

export interface ReferenceItem {
  id: string
  name: string
  is_active: boolean
  is_apci?: boolean // only present for 'diseases'
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

  return { search, create, update, deactivate }
}
