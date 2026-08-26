export type MedicationForm
  = | 'tablet'
    | 'capsule'
    | 'syrup'
    | 'suspension'
    | 'injection'
    | 'topical'
    | 'drops'
    | 'spray'
    | 'mouthwash'
    | 'gel'
    | 'cream'
    | 'paste'
    | 'varnish'
    | 'other'

export interface MedicationCatalogItem {
  id: string
  clinic_id: string
  name: string
  dose?: string | null
  unit?: string | null
  form: MedicationForm
  requires_prescription: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface MedicationCreatePayload {
  name: string
  dose?: string | null
  unit?: string | null
  form: MedicationForm
  requires_prescription?: boolean
  is_active?: boolean
}

export type MedicationUpdatePayload = Partial<MedicationCreatePayload>

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface MedicationListFilters {
  q?: string
  form?: MedicationForm
  is_active?: boolean
  page?: number
  page_size?: number
}

export function useMedicationCatalog() {
  const api = useApi()

  async function list(filters: MedicationListFilters = {}): Promise<ApiPaged<MedicationCatalogItem>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/medication_catalog/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<MedicationCatalogItem>>(url)
  }

  async function create(payload: MedicationCreatePayload): Promise<ApiOk<MedicationCatalogItem>> {
    return await api.post<ApiOk<MedicationCatalogItem>>('/api/v1/medication_catalog/', payload)
  }

  async function update(id: string, payload: MedicationUpdatePayload): Promise<ApiOk<MedicationCatalogItem>> {
    return await api.patch<ApiOk<MedicationCatalogItem>>(`/api/v1/medication_catalog/${id}`, payload)
  }

  async function remove(id: string): Promise<void> {
    await api.del(`/api/v1/medication_catalog/${id}`)
  }

  async function seed(): Promise<ApiOk<{ created: number, skipped: number }>> {
    return await api.post('/api/v1/medication_catalog/seed', {})
  }

  return { list, create, update, remove, seed }
}
