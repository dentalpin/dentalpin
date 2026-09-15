import type { ApiResponse } from '~~/app/types'

export interface AttendanceEvent {
  id: string
  user_id: string
  kind: 'in' | 'out'
  at: string
  note: string | null
}

export interface AttendanceStatus {
  user_id: string
  state: 'in' | 'out'
  since: string | null
}

export interface AttendanceReportRow {
  user_id: string
  full_name: string
  seconds: number
  open: boolean
}

export interface StaffMember {
  id: string
  first_name: string
  last_name: string
  role: string
}

export function useAttendance() {
  const api = useApi()

  async function clock(userId: string, kind: 'in' | 'out', note?: string): Promise<AttendanceEvent> {
    const response = await api.post<ApiResponse<AttendanceEvent>>(
      '/api/v1/staff_attendance/events',
      { user_id: userId, kind, note: note ?? null }
    )
    return response.data
  }

  async function listEvents(day?: string): Promise<AttendanceEvent[]> {
    const response = await api.get<ApiResponse<AttendanceEvent[]>>(
      '/api/v1/staff_attendance/events',
      day ? { query: { day } } : {}
    )
    return response.data
  }

  async function getStatus(userId: string): Promise<AttendanceStatus> {
    const response = await api.get<ApiResponse<AttendanceStatus>>(
      `/api/v1/staff_attendance/status/${userId}`
    )
    return response.data
  }

  async function dailyReport(day: string): Promise<AttendanceReportRow[]> {
    const response = await api.get<ApiResponse<{ date: string, rows: AttendanceReportRow[] }>>(
      '/api/v1/staff_attendance/report',
      { query: { day } }
    )
    return response.data.rows
  }

  async function listStaff(): Promise<StaffMember[]> {
    const response = await api.get<ApiResponse<StaffMember[]>>('/api/v1/staff_attendance/members')
    return response.data
  }

  return { clock, listEvents, getStatus, dailyReport, listStaff }
}
