/**
 * Registers the Kapso WhatsApp connect page under Settings → Integrations.
 * Same boundary as the other modules: `~~` reaches the host shell only.
 */
import {
  registerGettingStartedRule,
  registerSettingsPage
} from '~~/app/composables/useSettingsRegistry'

interface KapsoOnboardingState { loaded: boolean, pending: boolean }

const useKapsoOnboardingState = () =>
  useState<KapsoOnboardingState>('whatsapp_kapso:onboarding', () => ({ loaded: false, pending: false }))

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'whatsapp-kapso',
    category: 'integrations',
    labelKey: 'whatsapp_kapso.settings.title',
    descriptionKey: 'whatsapp_kapso.settings.description',
    icon: 'i-lucide-message-circle',
    permission: 'whatsapp_kapso.settings.write',
    component: () => import('../components/KapsoSettingsPage.vue'),
    searchKeywords: ['whatsapp', 'kapso', 'mensajes', 'messages', 'integracion', 'integration'],
    order: 50
  })

  // Getting-started (issue #287): when the clinic's preferred channel is
  // WhatsApp but Kapso is not connected, every auto-send silently falls
  // back (or skips) — surface that as the primary nag. Availability is
  // read from the notifications settings API (`available_channels` is
  // computed via the adapter registry) — never by importing
  // notifications code (ADR 0016).
  registerGettingStartedRule({
    id: 'whatsapp_kapso',
    labelKey: 'whatsapp_kapso.onboarding.label',
    descriptionKey: 'whatsapp_kapso.onboarding.description',
    icon: 'i-lucide-message-circle',
    to: '/settings/whatsapp-kapso',
    order: 81,
    optional: true,
    severity: 'warning',
    load: async (api) => {
      const state = useKapsoOnboardingState()
      try {
        const res = await api.get<{ data: { preferred_channel?: string, available_channels?: string[] } }>(
          '/api/v1/notifications/settings'
        )
        const d = res.data
        state.value = {
          loaded: true,
          pending: d.preferred_channel === 'whatsapp'
            && !(d.available_channels ?? []).includes('whatsapp')
        }
      } catch {
        // No permission / transient error — don't nag.
        state.value = { loaded: true, pending: false }
      }
    },
    when: () => {
      const s = useKapsoOnboardingState().value
      return s.loaded && s.pending
    }
  })
})
