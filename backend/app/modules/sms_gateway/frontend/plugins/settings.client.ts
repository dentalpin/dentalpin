/**
 * Registers the SMS gateway settings page under Settings → Integrations.
 * Same pattern as whatsapp_kapso's settings.client.ts.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'sms-gateway',
    category: 'integrations',
    labelKey: 'sms_gateway.settings.title',
    descriptionKey: 'sms_gateway.settings.description',
    icon: 'i-lucide-message-square',
    permission: 'sms_gateway.settings.write',
    component: () => import('../components/SmsSettingsPage.vue'),
    searchKeywords: ['sms', 'text message', 'texto', 'sms provider'],
    order: 51
  })
})
