import type { ApiResponse } from '~~/app/types'

export interface AvailabilityRange {
  start: string
  end: string
  state: 'open' | 'clinic_closed' | 'professional_off'
  professional_id: string | null
  assistant_id?: string | null
  reason: string | null
}

export interface AvailabilityPayload {
  timezone: string
  ranges: AvailabilityRange[]
}

/**
 * Composable for schedules module pages (not for agenda — agenda has
 * its own 404-tolerant copy to preserve module isolation).
 */
export function useAvailability() {
  const api = useApi()

  async function fetch(params: { start: string, end: string, professional_id?: string, assistant_id?: string }): Promise<AvailabilityPayload> {
    const query = new URLSearchParams()
    query.set('start', params.start)
    query.set('end', params.end)
    if (params.professional_id) query.set('professional_id', params.professional_id)
    if (params.assistant_id) query.set('assistant_id', params.assistant_id)
    const res = await api.get<ApiResponse<AvailabilityPayload>>(`/api/v1/schedules/availability?${query.toString()}`)
    return res.data
  }

  return { fetch }
}
