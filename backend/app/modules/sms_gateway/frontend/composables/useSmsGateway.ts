export interface SmsSettings {
  provider_name: string
  sender_id: string | null
  base_url: string | null
  has_api_key: boolean
  is_active: boolean
}

export interface SmsSettingsUpdatePayload {
  provider_name?: string
  api_key?: string
  sender_id?: string | null
  base_url?: string | null
  is_active?: boolean
}

export interface SmsOutboxLogEntry {
  id: string
  to_address: string
  body: string
  provider_name: string
  status: string
  error_message: string | null
  created_at: string
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export function useSmsGateway() {
  const api = useApi()
  const settings = ref<SmsSettings | null>(null)
  const providers = ref<string[]>([])
  const outbox = ref<SmsOutboxLogEntry[]>([])
  const loading = ref(false)
  const saving = ref(false)

  async function fetchProviders() {
    const res = await api.get<ApiOk<string[]>>('/api/v1/sms_gateway/providers')
    providers.value = res.data
  }

  async function fetchSettings() {
    loading.value = true
    try {
      const res = await api.get<ApiOk<SmsSettings>>('/api/v1/sms_gateway/settings')
      settings.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function saveSettings(payload: SmsSettingsUpdatePayload) {
    saving.value = true
    try {
      const res = await api.patch<ApiOk<SmsSettings>>('/api/v1/sms_gateway/settings', payload)
      settings.value = res.data
    } finally {
      saving.value = false
    }
  }

  async function fetchOutbox() {
    const res = await api.get<ApiPaged<SmsOutboxLogEntry>>('/api/v1/sms_gateway/outbox?page=1&page_size=20')
    outbox.value = res.data
  }

  return { settings, providers, outbox, loading, saving, fetchProviders, fetchSettings, saveSettings, fetchOutbox }
}
