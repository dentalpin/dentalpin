/**
 * Registers the copilot settings page on the host registry. Mounted
 * as a card under ``/settings/integrations`` and as a full page at
 * ``/settings/integrations/copilot``.
 *
 * `~~` reaches the frontend host shell, not another module — copilot's
 * depends stay at ``[]``.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'copilot',
    category: 'integrations',
    labelKey: 'copilot.settings.title',
    descriptionKey: 'copilot.settings.description',
    icon: 'i-lucide-sparkles',
    permission: PERMISSIONS.copilot.configure,
    component: () => import('../components/CopilotSettingsPanel.vue'),
    searchKeywords: ['copilot', 'ia', 'ai', 'briefing', 'digest', 'resumen'],
    order: 30
  })
})
