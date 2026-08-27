/**
 * Composable for sending appointment-related notifications.
 *
 * Provides helper functions to send confirmation, reminder, and
 * cancellation notifications on an explicit channel (email / WhatsApp).
 * When no channel is given the gateway resolves it from the clinic's
 * preferred-channel configuration (issue #287).
 */

import type { ApiResponse, ManualSendRequest, ManualSendResponse, NotificationChannel } from '~~/app/types'
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
   * Send an appointment-related notification, optionally on an explicit
   * channel (a staff Send button always names its channel).
   */
  async function sendAppointmentNotification(
    type: AppointmentNotificationType,
    appointmentId: string,
    patientId: string,
    channel?: NotificationChannel
  ): Promise<boolean> {
    isSending.value = true
    try {
      const payload: ManualSendRequest = {
        notification_type: type,
        appointment_id: appointmentId,
        patient_id: patientId
      }
      if (channel) {
        payload.channels = [channel]
      }
      const response = await api.post<ApiResponse<ManualSendResponse>>(
        '/api/v1/notifications/send',
        payload
      )
      if (response.data.success) {
        toast.add({
          title: t('common.success'),
          description: channel
            ? t(`notifications.channelSent.${channel}`)
            : t('appointments.emailSent'),
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
   * Send appointment confirmation
   */
  async function sendConfirmation(
    appointmentId: string,
    patientId: string,
    channel?: NotificationChannel
  ): Promise<boolean> {
    return sendAppointmentNotification('appointment_confirmation', appointmentId, patientId, channel)
  }

  /**
   * Send appointment reminder
   */
  async function sendReminder(
    appointmentId: string,
    patientId: string,
    channel?: NotificationChannel
  ): Promise<boolean> {
    return sendAppointmentNotification('appointment_reminder', appointmentId, patientId, channel)
  }

  /**
   * Send appointment cancellation notice
   */
  async function sendCancellation(
    appointmentId: string,
    patientId: string,
    channel?: NotificationChannel
  ): Promise<boolean> {
    return sendAppointmentNotification('appointment_cancelled', appointmentId, patientId, channel)
  }

  return {
    isSending: readonly(isSending),
    sendAppointmentNotification,
    sendConfirmation,
    sendReminder,
    sendCancellation
  }
}
