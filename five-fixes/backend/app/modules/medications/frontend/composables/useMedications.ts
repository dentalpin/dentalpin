// Matches frontend/app/composables/useApi.ts (confirmed against the
// real file): useApi() returns { get, post, put, patch, del, $api },
// each call takes the FULL /api/v1/... path, `query` for querystring
// params, and unwraps to ApiResponse<T> / PaginatedResponse<T>.

import type { ApiResponse, PaginatedResponse } from '~/types'

export type MedicationUnit = 'mg' | 'g' | 'ml' | 'UI' | '%' | 'other'

export type MedicationFormType =
  | 'tablet'
  | 'capsule'
  | 'syrup'
  | 'gel'
  | 'mouthwash'
  | 'injection'
  | 'cream'
  | 'other'

export interface Medication {
  id: string
  clinic_id: string
  name: string
  dose: number
  unit: MedicationUnit
  form: MedicationFormType
  times_per_day: number | null
  instructions: string | null
  is_prescribed: boolean
  created_at: string
  updated_at: string
}

export interface MedicationListParams {
  name?: string
  form?: MedicationFormType
  is_prescribed?: boolean
  page?: number
  page_size?: number
}

export interface MedicationInput {
  name: string
  dose: number
  unit: MedicationUnit
  form: MedicationFormType
  times_per_day?: number | null
  instructions?: string | null
  is_prescribed: boolean
}

export const useMedications = () => {
  const api = useApi()

  const list = (params: MedicationListParams = {}) =>
    api.get<PaginatedResponse<Medication>>('/api/v1/medications', {
      query: {
        name: params.name,
        form: params.form,
        is_prescribed: params.is_prescribed,
        page: params.page ?? 1,
        page_size: params.page_size ?? 1000,
      },
    })

  const get = async (id: string) => {
    const res = await api.get<ApiResponse<Medication>>(`/api/v1/medications/${id}`)
    return res.data
  }

  const create = async (data: MedicationInput) => {
    const res = await api.post<ApiResponse<Medication>>('/api/v1/medications', data)
    return res.data
  }

  const update = async (id: string, data: Partial<MedicationInput>) => {
    const res = await api.put<ApiResponse<Medication>>(`/api/v1/medications/${id}`, data)
    return res.data
  }

  const remove = (id: string) => api.del<void>(`/api/v1/medications/${id}`)

  return { list, get, create, update, remove }
}
