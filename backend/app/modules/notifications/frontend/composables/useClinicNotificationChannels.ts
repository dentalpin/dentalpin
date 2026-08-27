/**
 * Clinic-wide notification channel configuration for send surfaces.
 *
 * Every screen that renders a manual "Send" control (appointment modal,
 * quote send, invoice send) derives its buttons from the clinic's
 * `manual_channels` via `buttonsForPatient()` instead of hardcoding an
 * email checkbox. Issue #287.
 *
 * Shares the `notifications:settings` state with `useNotificationSettings`,
 * so a page that already called `fetchSettings()` needs no extra request.
 * `ensureLoaded()` is silent on failure (e.g. staff without
 * `notifications.settings.read`) and the computeds fall back to the
 * email-only defaults every clinic starts with.
 */

import type { ClinicNotificationSettings, NotificationChannel, ApiResponse } from '~~/app/types'

export interface ChannelButton {
  channel: NotificationChannel
  disabled: boolean
  reason?: 'no_email' | 'no_phone' | 'channel_not_manual'
}

export interface PatientContact {
  email?: string | null
  phone?: string | null
}

/** Stable render order — email first, then WhatsApp. */
const CHANNEL_ORDER: NotificationChannel[] = ['email', 'whatsapp']

export function useClinicNotificationChannels() {
  const api = useApi()

  // Same state key as useNotificationSettings — single source of truth.
  const settings = useState<ClinicNotificationSettings | null>('notifications:settings', () => null)
  const isLoading = useState<boolean>('notifications:channels:loading', () => false)

  const availableChannels = computed<string[]>(() => settings.value?.available_channels ?? ['email'])
  const preferredChannel = computed<string>(() => settings.value?.preferred_channel ?? 'email')
  const fallbackEnabled = computed<boolean>(() => settings.value?.fallback_enabled ?? true)
  const manualChannels = computed<string[]>(() => settings.value?.manual_channels ?? ['email'])

  /**
   * Fetch the clinic settings once, silently. Safe to call from screens
   * whose users may lack the settings.read permission — defaults apply.
   */
  async function ensureLoaded(): Promise<void> {
    if (settings.value || isLoading.value) return
    isLoading.value = true
    try {
      const response = await api.get<ApiResponse<ClinicNotificationSettings>>(
        '/api/v1/notifications/settings'
      )
      settings.value = response.data
    } catch {
      // 403 / network — keep null; computeds fall back to email-only.
    } finally {
      isLoading.value = false
    }
  }

  /**
   * One entry per clinic manual channel. A channel the patient cannot
   * receive is listed **disabled** (never hidden) with the reason, so
   * reception sees why the button is off.
   */
  function buttonsForPatient(patient: PatientContact | null | undefined): ChannelButton[] {
    const manual = manualChannels.value
    return CHANNEL_ORDER
      .filter(channel => manual.includes(channel))
      .map((channel) => {
        if (channel === 'email' && !patient?.email) {
          return { channel, disabled: true, reason: 'no_email' as const }
        }
        if (channel === 'whatsapp' && !patient?.phone) {
          return { channel, disabled: true, reason: 'no_phone' as const }
        }
        return { channel, disabled: false }
      })
  }

  return {
    isLoading: readonly(isLoading),
    availableChannels,
    preferredChannel,
    fallbackEnabled,
    manualChannels,
    ensureLoaded,
    buttonsForPatient
  }
}
