/**
 * Registers the telephony gateway page under Settings → Integrations.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'telephony',
    category: 'integrations',
    labelKey: 'telephony.settings.title',
    descriptionKey: 'telephony.settings.description',
    icon: 'i-lucide-phone-call',
    permission: PERMISSIONS.telephony.settingsWrite,
    component: () => import('../components/TelephonySettingsPage.vue'),
    searchKeywords: ['telefonia', 'telephony', 'cti', 'llamadas', 'calls', 'centralita', 'pbx'],
    order: 52
  })
})
