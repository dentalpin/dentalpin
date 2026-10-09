/**
 * Registers notifications-owned settings cards on the host registry.
 * Mounted under ``/settings/communications`` (the host shell exposes
 * a "communications" category — see ``useSettingsRegistry.ts``).
 *
 * Imports the registry from the host (``~~``) and never from another
 * module, keeping ``manifest.depends`` clean.
 */
import {
  registerGettingStartedRule,
  registerSettingsPage
} from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

interface SmtpOnboardingState { loaded: boolean, configured: boolean }

const useSmtpOnboardingState = () =>
  useState<SmtpOnboardingState>('notifications:onboarding-smtp', () => ({ loaded: false, configured: true }))

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'language',
    category: 'communications',
    labelKey: 'notifications.communications.language.cardTitle',
    descriptionKey: 'notifications.communications.language.cardDescription',
    icon: 'i-lucide-languages',
    permission: PERMISSIONS.admin.clinicWrite,
    component: () => import('../components/settings/ClinicLanguagePage.vue'),
    searchKeywords: [
      'idioma',
      'language',
      'comunicaciones',
      'communications',
      'patient',
      'paciente'
    ],
    order: 10
  })

  // Getting-started (optional): without an email sender the clinic can't
  // send confirmations / budgets. Global env SMTP counts as configured
  // only through the clinic-level override, so this stays advisory.
  registerGettingStartedRule({
    id: 'smtp',
    labelKey: 'notifications.onboarding.label',
    descriptionKey: 'notifications.onboarding.description',
    icon: 'i-lucide-mail',
    to: '/settings/notifications',
    permission: PERMISSIONS.notifications.settingsRead,
    order: 80,
    optional: true,
    severity: 'info',
    load: async (api) => {
      const state = useSmtpOnboardingState()
      const res = await api.get<{ data: { provider: string, from_email: string | null, has_password: boolean } }>(
        '/api/v1/notifications/smtp-settings'
      )
      const d = res.data
      state.value = {
        loaded: true,
        configured: d.provider !== 'smtp' ? d.provider !== 'disabled' : !!(d.from_email && d.has_password)
      }
    },
    when: () => {
      const s = useSmtpOnboardingState().value
      return s.loaded && !s.configured
    }
  })
})
