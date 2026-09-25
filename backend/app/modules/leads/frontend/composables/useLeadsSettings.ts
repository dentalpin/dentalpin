import type { ApiResponse } from '~~/app/types'

export interface LeadIntakeKeyStatus {
  configured: boolean
  key_prefix: string | null
  is_active: boolean
  last_used_at: string | null
}

export interface LeadSettings {
  daily_cap: number
  day_count: number
  day_count_date: string | null
  intake_url: string
  key: LeadIntakeKeyStatus
}

export interface IntakeKeyRotated {
  key: string
  key_prefix: string
}

export function useLeadsSettings() {
  const api = useApi()

  async function getSettings(): Promise<ApiResponse<LeadSettings>> {
    return await api.get<ApiResponse<LeadSettings>>('/api/v1/leads/settings')
  }

  async function updateSettings(dailyCap: number): Promise<ApiResponse<LeadSettings>> {
    return await api.patch<ApiResponse<LeadSettings>>(
      '/api/v1/leads/settings',
      { daily_cap: dailyCap },
      { errorToast: false }
    )
  }

  async function rotateIntakeKey(): Promise<ApiResponse<IntakeKeyRotated>> {
    return await api.post<ApiResponse<IntakeKeyRotated>>(
      '/api/v1/leads/settings/intake-key/rotate',
      undefined,
      { errorToast: false }
    )
  }

  async function setIntakeKeyActive(active: boolean): Promise<ApiResponse<LeadIntakeKeyStatus>> {
    return await api.patch<ApiResponse<LeadIntakeKeyStatus>>(
      '/api/v1/leads/settings/intake-key',
      { is_active: active },
      { errorToast: false }
    )
  }

  return { getSettings, updateSettings, rotateIntakeKey, setIntakeKeyActive }
}
