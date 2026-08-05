export interface TreatmentConsumable {
  id: string
  clinic_id: string
  treatment_id: string
  inventory_item_id: string
  quantity_needed: string
}

export interface TreatmentConsumableCreatePayload {
  treatment_id: string
  inventory_item_id: string
  quantity_needed: number
}

export interface TreatmentConsumableUpdatePayload {
  quantity_needed: number
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface TreatmentConsumableListFilters {
  treatment_id?: string
  inventory_item_id?: string
  page?: number
  page_size?: number
}

export function useTreatmentConsumables() {
  const api = useApi()

  async function list(filters: TreatmentConsumableListFilters = {}): Promise<ApiPaged<TreatmentConsumable>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/treatment_consumables/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<TreatmentConsumable>>(url)
  }

  async function create(payload: TreatmentConsumableCreatePayload): Promise<ApiOk<TreatmentConsumable>> {
    return await api.post<ApiOk<TreatmentConsumable>>('/api/v1/treatment_consumables/', payload)
  }

  async function update(id: string, payload: TreatmentConsumableUpdatePayload): Promise<ApiOk<TreatmentConsumable>> {
    return await api.patch<ApiOk<TreatmentConsumable>>(`/api/v1/treatment_consumables/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/treatment_consumables/${id}`)
  }

  return { list, create, update, remove }
}
