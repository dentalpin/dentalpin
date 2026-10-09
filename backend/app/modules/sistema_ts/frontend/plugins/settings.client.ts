/**
 * Sistema Tessera Sanitaria pages under Settings → Billing: registry pages,
 * no routes of their own. The connection page is gated on the configure
 * permission; the documents log is readable by billing roles.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'sistema-ts',
    category: 'billing',
    labelKey: 'sistema_ts.settings.title',
    descriptionKey: 'sistema_ts.settings.description',
    icon: 'i-lucide-heart-pulse',
    permission: PERMISSIONS.sistemaTs.settingsConfigure,
    component: () => import('../components/SistemaTsSettingsPage.vue'),
    searchKeywords: ['sistema ts', 'tessera sanitaria', '730', 'precompilata', 'spese sanitarie', 'italy', 'italia'],
    order: 64
  })
  registerSettingsPage({
    path: 'sistema-ts-documents',
    category: 'billing',
    labelKey: 'sistema_ts.documents.title',
    descriptionKey: 'sistema_ts.documents.description',
    icon: 'i-lucide-list-checks',
    permission: PERMISSIONS.sistemaTs.documentsRead,
    component: () => import('../components/SistemaTsDocumentsPage.vue'),
    searchKeywords: ['sistema ts', 'tessera sanitaria', 'protocollo', 'spese', 'documents'],
    order: 65
  })
})
