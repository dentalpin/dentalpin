/**
 * Registers the WhatsApp webhook page under Settings → Integrations.
 * Same boundary as the other modules: `~~` reaches the host shell only.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'whatsapp-webhook',
    category: 'integrations',
    labelKey: 'whatsapp_webhook.settings.title',
    descriptionKey: 'whatsapp_webhook.settings.description',
    icon: 'i-lucide-webhook',
    permission: PERMISSIONS.whatsappWebhook.settingsWrite,
    component: () => import('../components/WebhookSettingsPage.vue'),
    searchKeywords: ['whatsapp', 'webhook', 'zapier', 'make', 'n8n', 'mensajes', 'messages'],
    order: 51
  })
})
