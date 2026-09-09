/**
 * Registers the SMS gateway settings page under Settings → Integrations.
 * Same boundary as the other modules: `~~` reaches the host shell only.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'sms-gateway',
    category: 'integrations',
    labelKey: 'sms_gateway.settings.title',
    descriptionKey: 'sms_gateway.settings.description',
    icon: 'i-lucide-message-square-text',
    permission: 'sms_gateway.settings.write',
    component: () => import('../components/SmsGatewaySettingsPage.vue'),
    searchKeywords: ['sms', 'gateway', 'mensajes', 'messages', 'integracion', 'integration', 'proveedor', 'provider'],
    order: 51
  })
})
