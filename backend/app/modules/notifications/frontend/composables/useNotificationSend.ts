/**
 * Composable for sending appointment-related notifications.
 *
 * Provides helper functions to send confirmation, reminder, and cancellation emails.
 */

import type { ApiResponse, ManualSendResponse } from '~~/app/types'
import { errorMessage } from '~~/app/utils/error'

export type AppointmentNotificationType
  = 'appointment_confirmation'
    | 'appointment_reminder'
    | 'appointment_cancelled'

export function useNotificationSend() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  const isSending = ref(false)

  /**
   * Send an appointment-related email notification
   */
  async function sendAppointmentEmail(
    type: AppointmentNotificationType,
    appointmentId: string,
    patientId: string
  ): Promise<boolean> {
    isSending.value = true
    try {
      const response = await api.post<ApiResponse<ManualSendResponse>>(
        '/api/v1/notifications/send',
        {
          notification_type: type,
          appointment_id: appointmentId,
          patient_id: patientId
        }
      )
      if (response.data.success) {
        toast.add({
          title: t('common.success'),
          description: t('appointments.emailSent'),
          color: 'success'
        })
        return true
      } else {
        toast.add({
          title: t('common.error'),
          description: response.data.message,
          color: 'error'
        })
        return false
      }
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('notifications.errors.send_failed')),
        color: 'error'
      })
      return false
    } finally {
      isSending.value = false
    }
  }

  /**
   * Send appointment confirmation email
   */
  async function sendConfirmation(appointmentId: string, patientId: string): Promise<boolean> {
    return sendAppointmentEmail('appointment_confirmation', appointmentId, patientId)
  }

  /**
   * Send appointment reminder email
   */
  async function sendReminder(appointmentId: string, patientId: string): Promise<boolean> {
    return sendAppointmentEmail('appointment_reminder', appointmentId, patientId)
  }

  /**
   * Send appointment cancellation email
   */
  async function sendCancellation(appointmentId: string, patientId: string): Promise<boolean> {
    return sendAppointmentEmail('appointment_cancelled', appointmentId, patientId)
  }

  return {
    isSending: readonly(isSending),
    sendAppointmentEmail,
    sendConfirmation,
    sendReminder,
    sendCancellation
  }
}
