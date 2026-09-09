/**
 * Composable for the SMS gateway settings page (issue #392 review).
 *
 * Provider credentials are write-only: they are sent on save and never
 * read back — responses expose `has_*` booleans only. The provider list
 * comes from `GET /providers`, so the UI can only offer backends that
 * exist server-side.
 */

import type { ApiResponse } from '~~/app/types'

export interface SmsGatewaySettings {
  id: string
  clinic_id: string
  provider: string
  from_number: string | null
  has_account_sid: boolean
  has_auth_token: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface SmsTestResult {
  configured: boolean
  would_send: boolean
  note?: string | null
}

export function useSmsGateway() {
  const api = useApi()

  async function fetchSettings() {
    return api.get<ApiResponse<SmsGatewaySettings>>('/api/v1/sms_gateway/settings')
  }

  async function saveSettings(payload: {
    provider?: string
    account_sid?: string | null
    auth_token?: string | null
    from_number?: string | null
    is_active?: boolean
  }) {
    return api.put<ApiResponse<SmsGatewaySettings>>('/api/v1/sms_gateway/settings', payload)
  }

  async function listProviders() {
    return api.get<ApiResponse<string[]>>('/api/v1/sms_gateway/providers')
  }

  async function testConnection() {
    return api.post<ApiResponse<SmsTestResult>>('/api/v1/sms_gateway/test', {})
  }

  return {
    fetchSettings,
    saveSettings,
    listProviders,
    testConnection
  }
}
