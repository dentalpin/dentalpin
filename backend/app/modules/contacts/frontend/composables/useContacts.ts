export type ContactType = 'lab' | 'supplier' | 'delegate' | 'other'

export interface Contact {
  id: string
  clinic_id: string
  name: string
  contact_type: ContactType
  phone?: string | null
  email?: string | null
  address?: string | null
  notes?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ContactCreatePayload {
  name: string
  contact_type: ContactType
  phone?: string | null
  email?: string | null
  address?: string | null
  notes?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface ContactListFilters {
  contact_type?: ContactType
  search?: string
  page?: number
  page_size?: number
}

export function useContacts() {
  const api = useApi()

  async function list(filters: ContactListFilters = {}): Promise<ApiPaged<Contact>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/contacts/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<Contact>>(url)
  }

  async function create(payload: ContactCreatePayload): Promise<ApiOk<Contact>> {
    return await api.post<ApiOk<Contact>>('/api/v1/contacts/', payload)
  }

  async function update(id: string, payload: Partial<ContactCreatePayload>): Promise<ApiOk<Contact>> {
    return await api.patch<ApiOk<Contact>>(`/api/v1/contacts/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/contacts/${id}`)
  }

  return { list, create, update, remove }
}
