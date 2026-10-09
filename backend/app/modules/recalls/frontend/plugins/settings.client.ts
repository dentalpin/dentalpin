/**
 * Registers the recalls settings page on the host registry. Mounted
 * as a card under ``/settings/clinical`` and as a full page at
 * ``/settings/clinical/recalls`` via the host's dynamic category
 * route.
 *
 * Same boundary as schedules — `~~` reaches the frontend host shell,
 * not another module. Recalls' depends stay at ``["patients", "agenda"]``.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'recalls',
    category: 'clinical',
    labelKey: 'recalls.settings.title',
    descriptionKey: 'recalls.settings.description',
    icon: 'i-lucide-bell',
    permission: PERMISSIONS.recalls.read,
    component: () => import('../components/RecallSettingsPanel.vue'),
    searchKeywords: ['recordatorio', 'recall', 'llamada', 'callback', 'motivo', 'intervalo'],
    order: 40
  })
})
