import type { ApiResponse } from '~~/app/types'

export interface ConversationMessage {
  id: string
  channel: string
  direction: 'outbound' | 'inbound'
  message_kind: string
  status: string
  sent_manually: boolean
  subject: string | null
  body_text: string | null
  template_key: string
  error_message: string | null
  created_at: string
  sent_at: string | null
  delivered_at: string | null
  read_at: string | null
}

const BASE = '/api/v1/notifications/conversations'

export function useConversation(patientId: string) {
  const api = useApi()
  const messages = ref<ConversationMessage[]>([])
  const loading = ref(false)
  const sending = ref(false)

  async function fetchThread(channel = 'whatsapp') {
    loading.value = true
    try {
      const res = await api.get<ApiResponse<ConversationMessage[]>>(
        `${BASE}/${patientId}?channel=${channel}`
      )
      messages.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function reply(body: string, channel = 'whatsapp') {
    // One reply at a time: a second Enter while the POST is in flight
    // would send the same WhatsApp message twice (#1231).
    if (sending.value) return false
    sending.value = true
    try {
      // 409 outside the 24h WhatsApp window is an expected branch — the
      // caller (ConversationThread) presents it, so no auto-toast here.
      const res = await api.post<ApiResponse<ConversationMessage>>(
        `${BASE}/${patientId}/reply`,
        { channel, body },
        { errorToast: false }
      )
      messages.value.push(res.data)
      return true
    } finally {
      sending.value = false
    }
  }

  return { messages, loading, sending, fetchThread, reply }
}
