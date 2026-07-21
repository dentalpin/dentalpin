export interface NotificationTemplate {
  id: string
  clinic_id: string | null
  template_key: string
  channel: string
  locale: string
  subject: string | null
  body_html: string | null
  body_text: string | null
  provider_template_name: string | null
  variables: Record<string, unknown> | null
  description: string | null
  is_active: boolean
  is_system: boolean
  created_at: string
  updated_at: string
}

export interface TemplateCreatePayload {
  template_key: string
  channel?: string
  locale?: string
  subject?: string | null
  body_html?: string | null
  body_text?: string | null
  provider_template_name?: string | null
  description?: string | null
  is_active?: boolean
}

export interface TemplateUpdatePayload {
  subject?: string | null
  body_html?: string | null
  body_text?: string | null
  description?: string | null
  is_active?: boolean
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export function useNotificationTemplates() {
  const api = useApi()

  async function list(): Promise<ApiPaged<NotificationTemplate>> {
    return await api.get<ApiPaged<NotificationTemplate>>('/api/v1/notifications/templates')
  }

  async function create(payload: TemplateCreatePayload): Promise<ApiOk<NotificationTemplate>> {
    return await api.post<ApiOk<NotificationTemplate>>('/api/v1/notifications/templates', payload)
  }

  async function update(id: string, payload: TemplateUpdatePayload): Promise<ApiOk<NotificationTemplate>> {
    return await api.put<ApiOk<NotificationTemplate>>(`/api/v1/notifications/templates/${id}`, payload)
  }

  async function remove(id: string): Promise<void> {
    await api.del(`/api/v1/notifications/templates/${id}`)
  }

  return { list, create, update, remove }
}
