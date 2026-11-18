import { defineAsyncComponent } from 'vue'
import { registerSlot } from '~~/app/composables/useModuleSlots'
import { PERMISSIONS } from '~~/app/config/permissions'

export default defineNuxtPlugin(() => {
  const active = useActiveModulesState()
  const installed = () => !!active.value?.some(module => module.name === 'whatsapp_manual')
  const button = defineAsyncComponent(() => import('../components/ManualWhatsAppButton.vue'))

  registerSlot('patient.summary.actions', {
    id: 'whatsapp_manual.patient.summary.actions',
    component: button,
    permission: PERMISSIONS.whatsappManual.write,
    condition: installed,
    order: 30
  })

  registerSlot('app.overlays', {
    id: 'whatsapp_manual.navigation-count',
    component: defineAsyncComponent(() => import('../components/ManualWhatsAppNavigation')),
    permission: PERMISSIONS.whatsappManual.read,
    condition: installed
  })
})
