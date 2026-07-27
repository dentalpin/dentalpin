export interface SupplierProfile {
  contact_id: string
  clinic_id: string
  website?: string | null
  payment_terms?: string | null
  lead_time_days?: number | null
  is_preferred: boolean
  created_at: string
  updated_at: string
}

export interface SupplierProfileUpsertPayload {
  website?: string | null
  payment_terms?: string | null
  lead_time_days?: number | null
  is_preferred?: boolean
}

// Flattened Contact + SupplierProfile view returned by GET /{id} and
// GET / — matches the backend's SupplierResponse schema.
export interface Supplier {
  contact_id: string
  name: string
  phone?: string | null
  email?: string | null
  address?: string | null
  notes?: string | null
  is_active: boolean
  website?: string | null
  payment_terms?: string | null
  lead_time_days?: number | null
  is_preferred: boolean
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface SupplierListFilters {
  search?: string
  is_preferred?: boolean
  page?: number
  page_size?: number
}

export function useSuppliers() {
  const api = useApi()

  async function list(filters: SupplierListFilters = {}): Promise<ApiPaged<Supplier>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    return await api.get<ApiPaged<Supplier>>(`/api/v1/suppliers/${qs.toString() ? `?${qs.toString()}` : ''}`)
  }

  // 404s if the contact has no profile row yet (i.e. never had
  // procurement fields set) — callers should catch that and fall back
  // to empty/default field values rather than treating it as an error.
  async function getSupplier(contactId: string): Promise<ApiOk<Supplier>> {
    return await api.get<ApiOk<Supplier>>(`/api/v1/suppliers/${contactId}`)
  }

  async function upsertProfile(
    contactId: string,
    payload: SupplierProfileUpsertPayload
  ): Promise<ApiOk<SupplierProfile>> {
    return await api.put<ApiOk<SupplierProfile>>(`/api/v1/suppliers/${contactId}`, payload)
  }

  async function removeProfile(contactId: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/suppliers/${contactId}`)
  }

  return { list, getSupplier, upsertProfile, removeProfile }
}
