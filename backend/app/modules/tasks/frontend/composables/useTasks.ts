export type TaskPriority = 'low' | 'normal' | 'high'
export type TaskStatus = 'open' | 'done'

export interface Task {
  id: string
  clinic_id: string
  title: string
  description?: string | null
  priority: TaskPriority
  status: TaskStatus
  assigned_to?: string | null
  assigned_to_name?: string | null
  assigned_by?: string | null
  assigned_by_name?: string | null
  due_date?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface AssignableUser {
  id: string
  full_name: string
  role: string
}

export interface TaskCreatePayload {
  title: string
  description?: string | null
  priority?: TaskPriority
  assigned_to?: string | null
  due_date?: string | null
}

export interface TaskUpdatePayload {
  title?: string
  description?: string | null
  priority?: TaskPriority
  status?: TaskStatus
  assigned_to?: string | null
  due_date?: string | null
}

interface ApiOk<T> { data: T, message?: string | null }
interface ApiPaged<T> { data: T[], total: number, page: number, page_size: number }

export interface TaskListFilters {
  task_status?: TaskStatus
  assigned_to?: string
  priority?: TaskPriority
  page?: number
  page_size?: number
}

export function useTasks() {
  const api = useApi()

  async function list(filters: TaskListFilters = {}): Promise<ApiPaged<Task>> {
    const qs = new URLSearchParams()
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue
      qs.append(k, String(v))
    }
    const url = `/api/v1/tasks/${qs.toString() ? `?${qs.toString()}` : ''}`
    return await api.get<ApiPaged<Task>>(url)
  }

  async function assignableUsers(): Promise<ApiOk<AssignableUser[]>> {
    return await api.get<ApiOk<AssignableUser[]>>('/api/v1/tasks/assignable-users')
  }

  async function create(payload: TaskCreatePayload): Promise<ApiOk<Task>> {
    return await api.post<ApiOk<Task>>('/api/v1/tasks/', payload)
  }

  async function update(id: string, payload: TaskUpdatePayload): Promise<ApiOk<Task>> {
    return await api.patch<ApiOk<Task>>(`/api/v1/tasks/${id}`, payload)
  }

  async function remove(id: string): Promise<ApiOk<null>> {
    return await api.del<ApiOk<null>>(`/api/v1/tasks/${id}`)
  }

  return { list, assignableUsers, create, update, remove }
}
