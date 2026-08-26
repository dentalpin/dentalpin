export interface ConsumableLink {
  id: string
  clinic_id: string
  catalog_item_id: string
  inventory_item_id: string
  quantity: string
  note?: string | null
  created_at: string
  updated_at: string
  // resolved by the API from both dependency modules
  treatment_name: string
  treatment_code?: string | null
  item_name: string
  item_unit?: string | null
}

export interface LinkOptionTreatment { id: string, name: string, internal_code?: string | null }
export interface LinkOptionItem { id: string, name: string, unit?: string | null }
export interface LinkOptions { treatments: LinkOptionTreatment[], items: LinkOptionItem[] }

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export function useTreatmentConsumables() {
  const api = useApi()

  async function list(filters: {
    catalog_item_id?: string
    inventory_item_id?: string
    page?: number
    page_size?: number
  } = {}): Promise<ApiPaged<ConsumableLink>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/treatment_consumables/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<ConsumableLink>>(url)
  }

  async function linkOptions(q?: string): Promise<ApiOk<LinkOptions>> {
    const url = `/api/v1/treatment_consumables/link-options${q ? `?q=${encodeURIComponent(q)}` : ''}`
    return await api.get<ApiOk<LinkOptions>>(url)
  }

  async function create(payload: {
    catalog_item_id: string
    inventory_item_id: string
    quantity: string
    note?: string | null
  }): Promise<ApiOk<ConsumableLink>> {
    return await api.post<ApiOk<ConsumableLink>>('/api/v1/treatment_consumables/', payload)
  }

  // `note: ''` clears the stored note; omitting it leaves it untouched.
  async function update(
    id: string,
    payload: { quantity: string, note?: string | null }
  ): Promise<ApiOk<ConsumableLink>> {
    return await api.patch<ApiOk<ConsumableLink>>(`/api/v1/treatment_consumables/${id}`, payload)
  }

  async function remove(id: string): Promise<void> {
    await api.del(`/api/v1/treatment_consumables/${id}`)
  }

  return { list, linkOptions, create, update, remove }
}
