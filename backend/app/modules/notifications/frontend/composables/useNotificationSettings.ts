/**
 * Composable for managing clinic notification settings.
 *
 * Provides methods to fetch, update, and test notification configuration.
 */

import { errorMessage } from '~~/app/utils/error'
import type {
  ApiResponse,
  ClinicNotificationSettings,
  ClinicNotificationSettingsUpdate,
  ManualSendRequest,
  ManualSendResponse,
  NotificationTypeSettings,
  SmtpSettings,
  SmtpSettingsUpdate,
  SmtpTestRequest,
  TestEmailResponse
} from '~~/app/types'

export function useNotificationSettings() {
  const api = useApi()
  const toast = useToast()
  const { t } = useI18n()

  // State
  const settings = useState<ClinicNotificationSettings | null>('notifications:settings', () => null)
  const smtpSettings = useState<SmtpSettings | null>('notifications:smtp', () => null)
  const isLoading = useState<boolean>('notifications:loading', () => false)
  const isSaving = useState<boolean>('notifications:saving', () => false)
  const isTesting = useState<boolean>('notifications:testing', () => false)
  const isSmtpLoading = useState<boolean>('notifications:smtp:loading', () => false)
  const isSmtpSaving = useState<boolean>('notifications:smtp:saving', () => false)
  const isSmtpTesting = useState<boolean>('notifications:smtp:testing', () => false)

  // Default notification types with their labels
  const notificationTypes = computed(() => [
    {
      key: 'appointment_confirmation',
      label: t('notifications.types.appointment_confirmation'),
      description: t('notifications.types.appointment_confirmation_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'appointment_cancelled',
      label: t('notifications.types.appointment_cancelled'),
      description: t('notifications.types.appointment_cancelled_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'appointment_reminder',
      label: t('notifications.types.appointment_reminder'),
      description: t('notifications.types.appointment_reminder_desc'),
      supportsHoursBefore: true
    },
    {
      key: 'budget_sent',
      label: t('notifications.types.budget_sent'),
      description: t('notifications.types.budget_sent_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'budget_accepted',
      label: t('notifications.types.budget_accepted'),
      description: t('notifications.types.budget_accepted_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'welcome',
      label: t('notifications.types.welcome'),
      description: t('notifications.types.welcome_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'invoice_sent',
      label: t('notifications.types.invoice_sent'),
      description: t('notifications.types.invoice_sent_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'budget_reminder',
      label: t('notifications.types.budget_reminder'),
      description: t('notifications.types.budget_reminder_desc'),
      supportsHoursBefore: false
    },
    {
      key: 'recall_reminder',
      label: t('notifications.types.recall_reminder'),
      description: t('notifications.types.recall_reminder_desc'),
      supportsHoursBefore: false
    }
  ])

  /**
   * Fetch clinic notification settings
   */
  async function fetchSettings(): Promise<void> {
    isLoading.value = true
    try {
      const response = await api.get<ApiResponse<ClinicNotificationSettings>>(
        '/api/v1/notifications/settings'
      )
      settings.value = response.data
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('notifications.errors.fetch_failed')),
        color: 'error'
      })
    } finally {
      isLoading.value = false
    }
  }

  /**
   * Update clinic notification settings
   */
  async function updateSettings(data: ClinicNotificationSettingsUpdate): Promise<boolean> {
    isSaving.value = true
    try {
      const response = await api.put<ApiResponse<ClinicNotificationSettings>>(
        '/api/v1/notifications/settings',
        data
      )
      settings.value = response.data
      toast.add({
        title: t('common.success'),
        description: t('notifications.settings_saved'),
        color: 'success'
      })
      return true
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('notifications.errors.save_failed')),
        color: 'error'
      })
      return false
    } finally {
      isSaving.value = false
    }
  }

  /**
   * Test email connection by sending a test email
   */
  async function testEmailConnection(toEmail: string): Promise<boolean> {
    isTesting.value = true
    try {
      const response = await api.post<ApiResponse<TestEmailResponse>>(
        '/api/v1/notifications/test',
        { to_email: toEmail }
      )
      if (response.data.success) {
        toast.add({
          title: t('common.success'),
          description: t('notifications.test_email_sent'),
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
        description: errorMessage(e, t('notifications.errors.test_failed')),
        color: 'error'
      })
      return false
    } finally {
      isTesting.value = false
    }
  }

  /**
   * Send a manual notification
   */
  async function sendNotification(request: ManualSendRequest): Promise<boolean> {
    try {
      const response = await api.post<ApiResponse<ManualSendResponse>>(
        '/api/v1/notifications/send',
        request
      )
      if (response.data.success) {
        toast.add({
          title: t('common.success'),
          description: response.data.message,
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
    }
  }

  /**
   * Get settings for a specific notification type
   */
  function getTypeSettings(notificationType: string): NotificationTypeSettings {
    return settings.value?.settings[notificationType] || {
      auto_send: true,
      enabled: true
    }
  }

  /**
   * Check if manual send button should be shown for a notification type
   */
  function shouldShowManualSend(notificationType: string): boolean {
    const typeSettings = getTypeSettings(notificationType)
    return typeSettings.enabled && !typeSettings.auto_send
  }

  /**
   * Check if a notification type is enabled
   */
  function isNotificationEnabled(notificationType: string): boolean {
    return getTypeSettings(notificationType).enabled
  }

  /**
   * Check if auto_send is enabled for a notification type
   */
  function getAutoSendStatus(notificationType: string): boolean {
    const typeSettings = getTypeSettings(notificationType)
    return typeSettings.enabled && typeSettings.auto_send
  }

  /**
   * Update a single notification type's settings
   */
  async function updateTypeSettings(
    notificationType: string,
    newSettings: Partial<NotificationTypeSettings>
  ): Promise<boolean> {
    const currentSettings = settings.value?.settings || {}
    const updatedSettings: Record<string, Partial<NotificationTypeSettings>> = {
      [notificationType]: {
        ...currentSettings[notificationType],
        ...newSettings
      }
    }
    return await updateSettings({ settings: updatedSettings })
  }

  // ========================================================================
  // SMTP Settings
  // ========================================================================

  /**
   * Fetch SMTP settings for the clinic
   */
  async function fetchSmtpSettings(): Promise<void> {
    isSmtpLoading.value = true
    try {
      const response = await api.get<ApiResponse<SmtpSettings>>(
        '/api/v1/notifications/smtp-settings'
      )
      smtpSettings.value = response.data
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('notifications.smtp.errors.fetch_failed')),
        color: 'error'
      })
    } finally {
      isSmtpLoading.value = false
    }
  }

  /**
   * Update SMTP settings for the clinic
   */
  async function updateSmtpSettings(data: SmtpSettingsUpdate): Promise<boolean> {
    isSmtpSaving.value = true
    try {
      const response = await api.put<ApiResponse<SmtpSettings>>(
        '/api/v1/notifications/smtp-settings',
        data
      )
      smtpSettings.value = response.data
      toast.add({
        title: t('common.success'),
        description: t('notifications.smtp.settings_saved'),
        color: 'success'
      })
      return true
    } catch (e) {
      toast.add({
        title: t('common.error'),
        description: errorMessage(e, t('notifications.smtp.errors.save_failed')),
        color: 'error'
      })
      return false
    } finally {
      isSmtpSaving.value = false
    }
  }

  /**
   * Test SMTP connection with specific settings
   */
  async function testSmtpConnection(request: SmtpTestRequest): Promise<boolean> {
    isSmtpTesting.value = true
    try {
      const response = await api.post<ApiResponse<TestEmailResponse>>(
        '/api/v1/notifications/smtp-settings/test',
        request
      )
      if (response.data.success) {
        toast.add({
          title: t('common.success'),
          description: t('notifications.smtp.test_success'),
          color: 'success'
        })
        // Refresh SMTP settings to get updated verification status
        await fetchSmtpSettings()
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
        description: errorMessage(e, t('notifications.smtp.errors.test_failed')),
        color: 'error'
      })
      return false
    } finally {
      isSmtpTesting.value = false
    }
  }

  return {
    // State
    settings: readonly(settings),
    smtpSettings: readonly(smtpSettings),
    isLoading: readonly(isLoading),
    isSaving: readonly(isSaving),
    isTesting: readonly(isTesting),
    isSmtpLoading: readonly(isSmtpLoading),
    isSmtpSaving: readonly(isSmtpSaving),
    isSmtpTesting: readonly(isSmtpTesting),
    notificationTypes,

    // Actions
    fetchSettings,
    updateSettings,
    testEmailConnection,
    sendNotification,

    // SMTP Actions
    fetchSmtpSettings,
    updateSmtpSettings,
    testSmtpConnection,

    // Helpers
    getTypeSettings,
    shouldShowManualSend,
    isNotificationEnabled,
    getAutoSendStatus,
    updateTypeSettings
  }
}
