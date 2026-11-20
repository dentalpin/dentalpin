import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { registerSettingsPage } from '~~/app/composables/useSettingsRegistry'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  registerSlot('patient.detail.tabs', {
    id: 'gdpr-access-log',
    component: defineAsyncComponent(() => import('../components/PatientAccessLogTab.vue')),
    labelKey: 'gdprAccess.patientTab',
    permission: PERMISSIONS.gdpr.accessLogRead
  })
  registerSettingsPage({
    path: 'patient-access-log',
    category: 'people',
    labelKey: 'gdprAccess.settings',
    icon: 'i-lucide-shield',
    permission: PERMISSIONS.gdpr.accessLogRead,
    component: () => import('../components/AccessLogSettings.vue')
  })
})
