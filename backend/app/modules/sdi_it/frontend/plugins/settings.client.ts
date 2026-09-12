/**
 * SDI (FatturaPA) pages under Settings → Billing: registry pages, no
 * routes of their own. The connection page is gated on the configure
 * permission; the records log is readable by billing roles.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'sdi-it',
    category: 'billing',
    labelKey: 'sdi_it.settings.title',
    descriptionKey: 'sdi_it.settings.description',
    icon: 'i-lucide-file-check-2',
    permission: 'sdi_it.settings.configure',
    component: () => import('../components/SdiItSettingsPage.vue'),
    searchKeywords: ['sdi', 'fatturapa', 'fattura elettronica', 'pec', 'agenzia delle entrate', 'italy', 'italia'],
    order: 62
  })
  registerSettingsPage({
    path: 'sdi-it-records',
    category: 'billing',
    labelKey: 'sdi_it.records.title',
    descriptionKey: 'sdi_it.records.description',
    icon: 'i-lucide-list-checks',
    permission: 'sdi_it.records.read',
    component: () => import('../components/SdiItRecordsPage.vue'),
    searchKeywords: ['sdi', 'fattura', 'ricevuta', 'scarto', 'records'],
    order: 63
  })
})
