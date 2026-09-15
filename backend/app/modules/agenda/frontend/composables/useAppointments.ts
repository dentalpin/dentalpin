import type { Appointment, AppointmentCreate, AppointmentStatus, AppointmentUpdate, PaginatedResponse, ApiResponse } from '~~/app/types'

export function useAppointments() {
  const api = useApi()

  // State
  const appointments = useState<Appointment[]>('appointments:list', () => [])
  const isLoading = useState<boolean>('appointments:loading', () => false)
  const error = useState<string | null>('appointments:error', () => null)

  // Whenever the loaded appointments change (initial fetch, navigation,
  // mutation), refresh the "has notes" indicator for the new id set.
  // Guarded by a single ``useState`` flag so the watcher is wired
  // exactly once across the whole app, regardless of how many
  // components call ``useAppointments``.
  if (import.meta.client) {
    const wired = useState<boolean>('appointments:notes-indicator-wired', () => false)
    if (!wired.value) {
      wired.value = true
      const notesIndicator = useAppointmentNotesIndicator()
      watch(
        appointments,
        (list) => {
          notesIndicator.fetchFor(list.map(a => a.id))
        },
        { immediate: true }
      )
    }
  }

  // Actions
  async function fetchAppointments(startDate: Date, endDate: Date): Promise<Appointment[]> {
    isLoading.value = true
    error.value = null

    try {
      const params = new URLSearchParams({
        start_date: startDate.toISOString(),
        end_date: endDate.toISOString(),
        page_size: '500'
      })

      // Callers render `error` as the #101 load-error banner.
      const response = await api.get<PaginatedResponse<Appointment>>(
        `/api/v1/agenda/appointments?${params.toString()}`,
        { errorToast: false }
      )

      appointments.value = response.data
      return response.data
    } catch (e) {
      error.value = 'Failed to fetch appointments'
      console.error('Failed to fetch appointments:', e)
      return []
    } finally {
      isLoading.value = false
    }
  }

  async function createAppointment(data: AppointmentCreate): Promise<Appointment> {
    // Callers catch and present (409 conflict copy, form toasts).
    const response = await api.post<ApiResponse<Appointment>>(
      '/api/v1/agenda/appointments',
      data,
      { errorToast: false }
    )

    // Add to local state
    appointments.value = [...appointments.value, response.data]

    return response.data
  }

  async function updateAppointment(id: string, data: AppointmentUpdate): Promise<Appointment> {
    // Callers catch and present (409 conflict copy, form toasts).
    const response = await api.put<ApiResponse<Appointment>>(
      `/api/v1/agenda/appointments/${id}`,
      data,
      { errorToast: false }
    )

    // Update local state
    appointments.value = appointments.value.map(apt =>
      apt.id === id ? response.data : apt
    )

    return response.data
  }

  async function cancelAppointment(id: string): Promise<void> {
    // Caller (AppointmentModal) catches and toasts errorMessage.
    await api.del(`/api/v1/agenda/appointments/${id}`, { errorToast: false })

    // Update local state - mark as cancelled
    appointments.value = appointments.value.map(apt =>
      apt.id === id ? { ...apt, status: 'cancelled' as const } : apt
    )
  }

  async function updateAppointmentStatus(id: string, status: Appointment['status']): Promise<Appointment> {
    return await updateAppointment(id, { status })
  }

  /**
   * Assign, reassign or unassign (``cabinet_id=null``) a cabinet.
   * Optimistic local update + rollback on failure.
   */
  async function assignCabinet(
    id: string,
    cabinetId: string | null,
    note?: string
  ): Promise<Appointment> {
    const previous = appointments.value.find(apt => apt.id === id)
    const optimisticNow = new Date().toISOString()

    if (previous) {
      appointments.value = appointments.value.map(apt =>
        apt.id === id
          ? {
              ...apt,
              cabinet_id: cabinetId,
              cabinet: cabinetId === null ? null : apt.cabinet,
              cabinet_assigned_at: cabinetId === null ? null : optimisticNow
            }
          : apt
      )
    }

    try {
      // Callers catch the rethrow and toast the conflict themselves.
      const response = await api.patch<ApiResponse<Appointment>>(
        `/api/v1/agenda/appointments/${id}/cabinet`,
        { cabinet_id: cabinetId, note: note ?? null },
        { errorToast: false }
      )
      appointments.value = appointments.value.map(apt =>
        apt.id === id ? response.data : apt
      )
      return response.data
    } catch (err) {
      if (previous) {
        appointments.value = appointments.value.map(apt =>
          apt.id === id ? previous : apt
        )
      }
      throw err
    }
  }

  /**
   * Transition an appointment through the status lifecycle. Updates the
   * local list optimistically (``status`` + ``current_status_since``) and
   * rolls back on failure. Returns the server's authoritative response.
   */
  async function transition(
    id: string,
    to: AppointmentStatus,
    note?: string
  ): Promise<Appointment> {
    const previous = appointments.value.find(apt => apt.id === id)
    const optimisticSince = new Date().toISOString()

    if (previous) {
      appointments.value = appointments.value.map(apt =>
        apt.id === id
          ? { ...apt, status: to, current_status_since: optimisticSince }
          : apt
      )
    }

    try {
      // Callers catch the rethrow and toast the failed transition.
      const response = await api.post<ApiResponse<Appointment>>(
        `/api/v1/agenda/appointments/${id}/transitions`,
        { to_status: to, note: note ?? null },
        { errorToast: false }
      )
      appointments.value = appointments.value.map(apt =>
        apt.id === id ? response.data : apt
      )
      return response.data
    } catch (err) {
      if (previous) {
        appointments.value = appointments.value.map(apt =>
          apt.id === id ? previous : apt
        )
      }
      throw err
    }
  }

  /** Mint a short-lived QR check-in token for an appointment. */
  async function mintCheckinToken(id: string): Promise<{ token: string, expires_at: string }> {
    const response = await api.post<ApiResponse<{ token: string, expires_at: string }>>(
      `/api/v1/agenda/appointments/${id}/check-in-token`
    )
    return response.data
  }

  /**
   * Fetch the check-in QR PNG as an object URL. Uses `useApi.raw`
   * (session-cookie auth + refresh/retry + CSRF) because `<img>` needs
   * bytes and the download should authenticate like every other call.
   */
  async function fetchCheckinQr(id: string): Promise<string> {
    const origin = import.meta.client ? window.location.origin : ''
    const response = await api.raw(
      `/api/v1/agenda/appointments/${id}/check-in-qr?origin=${encodeURIComponent(origin)}`
    )
    if (!response.ok) throw new Error(`check-in QR: ${response.status}`)
    return URL.createObjectURL(await response.blob())
  }

  return {
    // shallowReadonly: consumers cannot swap the list, while elements keep
    // their `Appointment` type — the deep `readonly()` view forces
    // DeepReadonly<Appointment> through every child prop and emit.
    appointments: shallowReadonly(appointments),
    isLoading: readonly(isLoading),
    error: readonly(error),
    fetchAppointments,
    createAppointment,
    updateAppointment,
    cancelAppointment,
    updateAppointmentStatus,
    transition,
    assignCabinet,
    mintCheckinToken,
    fetchCheckinQr
  }
}
