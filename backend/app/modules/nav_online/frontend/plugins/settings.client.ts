/**
 * NAV Online Számla pages under Settings → Billing (registry pages, no
 * routes of their own). Gated on the configure permission for the
 * connection page; the records log is readable by billing roles.
 */
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'

export default defineNuxtPlugin(() => {
  registerSettingsPage({
    path: 'nav-online',
    category: 'billing',
    labelKey: 'nav_online.settings.title',
    descriptionKey: 'nav_online.settings.description',
    icon: 'i-lucide-landmark',
    permission: 'nav_online.settings.configure',
    component: () => import('../components/NavOnlineSettingsPage.vue'),
    searchKeywords: ['nav', 'online számla', 'adószám', 'hungary', 'magyar', 'invoice reporting'],
    order: 60
  })
  registerSettingsPage({
    path: 'nav-online-records',
    category: 'billing',
    labelKey: 'nav_online.records.title',
    descriptionKey: 'nav_online.records.description',
    icon: 'i-lucide-list-checks',
    permission: 'nav_online.records.read',
    component: () => import('../components/NavOnlineRecordsPage.vue'),
    searchKeywords: ['nav', 'számla', 'beküldés', 'records', 'queue'],
    order: 61
  })
})
